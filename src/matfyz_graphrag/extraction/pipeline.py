"""Pipeline for extracting deterministic NLP graph features from raw text.

This module implements the core stages of the GraphRAG pipeline:
1. Data Ingestion
2. Named Entity Recognition (via NameTag 3)
3. Relation Extraction (via RobeCzech)
4. Graph Serialization
"""

import json
from pathlib import Path

try:
    from transformers import pipeline  # type: ignore
except ImportError:
    pipeline = None


def read_raw_text(file_path: Path) -> str:
    """Reads raw Czech text from a specified file.

    Args:
        file_path (Path): Path to the input text file.

    Returns:
        str: The complete raw text content of the file.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        IsADirectoryError: If the specified path is a directory instead of a file.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"Raw data file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def extract_entities_with_nametag(text: str, model_dir: Path) -> list[dict]:
    """Extracts named entities using the locally cloned NameTag 3 model.

    This function utilizes the `nametag3_server` implementation to securely
    load the TensorFlow/Keras architecture without spinning up a REST endpoint.

    Args:
        text (str): The raw text to process.
        model_dir (Path): Path to the directory containing NameTag 3 weights
            (e.g., data/external/).

    Returns:
        list[dict]: A list of extracted entities with 'entity' and 'type'.

    Raises:
        FileNotFoundError: If the NameTag 3 directory is malformed.
        RuntimeError: If TensorFlow or the nametag3 internal inference module fails.
    """
    import sys

    if not (model_dir / "checkpoint.weights.h5").is_file():
        raise FileNotFoundError(f"NameTag 3 weights not found in {model_dir}")

    # Add the cloned repository to the python path dynamically
    nametag_repo = Path(__file__).parent / "nametag3"
    if str(nametag_repo) not in sys.path:
        sys.path.append(str(nametag_repo))

    try:
        from nametag3_dataset_collection import NameTag3DatasetCollection
        from nametag3_server import Models
    except ImportError as e:
        raise RuntimeError(f"Failed to import nametag3 local module: {e}")

    # Mock server arguments required by the model initialization
    class ServerConfig:
        batch_size = 32
        max_labels_per_token = 5

    # Load the actual neural network offline
    print(f"Loading NameTag 3 Tensor Graph from {model_dir}...")
    model_wrapper = Models.Model(
        path=str(model_dir),
        name="czech_cnec_offline",
        acknowledgements="",
        server_args=ServerConfig(),
    )

    sentences = list(model_wrapper._udpipe_tokenizer.tokenize(text, "untokenized"))

    # Extract raw input strings from the UDPipe structures
    input_tokens = []
    for sentence in sentences:
        for word in sentence.words[1:]:  # UDPipe 1-indexes actual words
            input_tokens.append(word.form)
        input_tokens.append("")  # NameTag3 expects empty strings between sentences

    # 2. Package those sentences securely into the dataset collection
    test_collection = NameTag3DatasetCollection(
        model_wrapper.args,
        tokenizer=model_wrapper.hf_tokenizer,
        text="\n".join(input_tokens),
        train_collection=model_wrapper._train_collection,
        tagsets=None,
    )

    # 3. Iterate through the model's prediction generator
    extracted_entities = []

    for batch_output in model_wrapper.model.yield_predicted_batches(
        "test", test_collection.datasets[-1], model_wrapper.args
    ):
        # NameTag yields lists of un-postprocessed strings per batch.
        # You must join them and resolve nesting postprocessing first!
        joined_output = "".join(batch_output)
        clean_output = model_wrapper.postprocess(joined_output)

        current_entity = None

        for line in clean_output.split("\n"):
            line = line.strip()
            if not line:
                continue

            cols = line.split("\t")
            if len(cols) < 2:
                continue

            form = cols[0]
            # Take only the top-level entity if it's nested (e.g., 'B-P|B-pf' -> 'B-P')
            tag = cols[1].split("|")[0]

            if tag.startswith("B-"):
                if current_entity:
                    extracted_entities.append(current_entity)
                current_entity = {
                    "entity": form,
                    "type": tag[
                        2:
                    ],  # Strip the "B-" prefix to just get the type (e.g. "P")
                }

            elif (
                tag.startswith("I-")
                and current_entity
                and current_entity["type"] == tag[2:]
            ):
                # Continue attaching words to the existing entity
                current_entity["entity"] += " " + form

            elif tag == "O":
                # The entity has concluded
                if current_entity:
                    extracted_entities.append(current_entity)
                    current_entity = None

        # Catch any entity that was still open at the very end of the batch text
        if current_entity:
            extracted_entities.append(current_entity)

    return extracted_entities


def extract_relations_with_ollama(
    entities: list[dict], text: str, model_id: str = "llama3"
) -> list[dict]:
    """Identifies relations between entities using a local Ollama SLM.

    Executes a zero-shot prompt via the local Ollama API to semantically
    link extracted entities across the provided text.

    Args:
        entities (list[dict]): Entities previously extracted by NameTag.
        text (str): The original text context.
        model_id (str): The local Ollama model to invoke (default: 'llama3').

    Returns:
        list[dict]: Predicted relations with 'source', 'target', and 'relation_type'.

    Raises:
        ConnectionError: If the local Ollama server is not running on port 11434.
    """
    import json
    import urllib.error
    import urllib.request

    if len(entities) < 2:
        return []

    # Construct a deterministic JSON extraction prompt for the SLM
    entity_names = [e["entity"] for e in entities]
    prompt = f"""
You are a strict, deterministic Czech NLP Graph extraction assistant.
Analyze the following sentence and extract the relations between these
specific entities: {entity_names}.
Sentence: "{text}"

Output strictly a JSON array of objects with the keys "source", "target",
and "relation_type".
Do not output any markdown formatting, only the JSON.
Keep the relation_type capitalized (e.g. VISITED, EMPLOYEE_OF).
"""

    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=json.dumps(
                {"model": model_id, "prompt": prompt, "format": "json", "stream": False}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))

        # Parse the JSON response enforcing the schema
        try:
            raw_response = result.get("response", "[]")
            relations = json.loads(raw_response)

            if isinstance(relations, list):
                return relations
            elif isinstance(relations, dict):
                # Generative models often wrap arrays in a dictionary!
                for key, value in relations.items():
                    if isinstance(value, list):
                        return value
                print(f"Ollama returned a dict but no list was found: {raw_response}")
                return [relations]
            else:
                print(f"Ollama returned an unexpected Data Type: {raw_response}")
                return []

        except json.JSONDecodeError:
            print(f"Ollama returned malformed JSON: {raw_response}")
            return []

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise ConnectionError(f"Ollama returned HTTP {e.code}: {error_body}")
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Failed to connect to local Ollama on port 11434. "
            f"Is it running? Error: {e}"
        )


def save_local_graph(
    entities: list[dict], relations: list[dict], output_path: Path
) -> None:
    """Serializes the extracted entities and relations into JSON format.

    Args:
        entities (list[dict]): The List of extracted named entities.
        relations (list[dict]): The List of extracted relations bridging entities.
        output_path (Path): Path where the JSON file will be saved.

    Raises:
        IOError: If writing to the specified path fails.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    graph_data = {"entities": entities, "relations": relations}

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    from pathlib import Path

    dummy_text = "Prezident Petr Pavel včera přijel na Karlovu univerzitu v Praze."

    # Your zip files were extracted directly into data/external/,
    # not into a subfolder!
    cnec_model_dir = Path("data/external")

    print("Testing NameTag 3 Extraction...")
    entities = extract_entities_with_nametag(dummy_text, cnec_model_dir)
    for e in entities:
        print(f"  Entity Found: {e}")

    print("\nTesting Ollama Relation Extraction...")
    try:
        relations = extract_relations_with_ollama(
            entities, dummy_text, model_id="llama3:8b"
        )
        for r in relations:
            print(f"  Relation Found: {r}")
    except ConnectionError as e:
        print(f"  [Skipped] {e}")
