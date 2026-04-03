"""
Ontology generation service
Interface 1: Analyze text content and generate entity and relationship type definitions suitable for social simulation
"""

import json
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient


# System prompt for ontology generation
ONTOLOGY_SYSTEM_PROMPT = """You are a professional knowledge graph ontology design expert. Your task is to analyze given text content and simulation requirements, and design entity types and relationship types suitable for **social media opinion simulation**.

**Important: You must output valid JSON format data, do not output anything else.**

## Core Task Background

We are building a **social media opinion simulation system**. In this system:
- Each entity is an "account" or "subject" that can voice, interact, and spread information on social media
- Entities influence each other, retweet, comment, and respond
- We need to simulate the reactions of various parties in opinion events and information dissemination paths

Therefore, **entities must be real-world entities that can voice and interact on social media**:

**Can be**:
- Specific individuals (public figures, stakeholders, opinion leaders, experts, ordinary people)
- Companies and enterprises (including their official accounts)
- Organizations (universities, associations, NGOs, unions, etc.)
- Government departments and regulatory agencies
- Media institutions (newspapers, TV stations, self-media, websites)
- Social media platforms themselves
- Specific group representatives (such as alumni associations, fan groups, rights protection groups, etc.)

**Cannot be**:
- Abstract concepts (such as "public opinion", "emotion", "trend")
- Topics/subjects (such as "academic integrity", "education reform")
- Views/attitudes (such as "supporters", "opponents")

## Output Format

Please output JSON format with the following structure:

```json
{
    "entity_types": [
        {
            "name": "Entity type name (English, PascalCase)",
            "description": "Brief description (English, no more than 100 characters)",
            "attributes": [
                {
                    "name": "Attribute name (English, snake_case)",
                    "type": "text",
                    "description": "Attribute description"
                }
            ],
            "examples": ["Example entity 1", "Example entity 2"]
        }
    ],
    "edge_types": [
        {
            "name": "Relationship type name (English, UPPER_SNAKE_CASE)",
            "description": "Brief description (English, no more than 100 characters)",
            "source_targets": [
                {"source": "Source entity type", "target": "Target entity type"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "Brief analysis and explanation of text content"
}
```

## Design Guidelines (Extremely Important!)

### 1. Entity Type Design - Must Strictly Follow

**Quantity requirement: Must have exactly 10 entity types**

**Hierarchical structure requirement (must include both specific types and fallback types)**:

Your 10 entity types must include the following hierarchy:

A. **Fallback types (must include, place in last 2 of list)**:
   - `Person`: Fallback type for any natural person. When a person does not fit other more specific person types, use this.
   - `Organization`: Fallback type for any organization. When an organization does not fit other more specific organization types, use this.

B. **Specific types (8, designed based on text content)**:
   - Design more specific types for main characters appearing in the text
   - Example: If text involves academic events, can have `Student`, `Professor`, `University`
   - Example: If text involves business events, can have `Company`, `CEO`, `Employee`

**Why fallback types are needed**:
- Various people will appear in the text, such as "primary/secondary teachers", "random person", "some netizen"
- If no specific type matches, they should be classified as `Person`
- Similarly, small organizations and temporary groups should be classified as `Organization`

**Design principles for specific types**:
- Identify high-frequency or key role types from the text
- Each specific type should have clear boundaries, avoid overlap
- Description must clearly explain the difference between this type and the fallback type

### 2. Relationship Type Design

- Quantity: 6-10
- Relationships should reflect real connections in social media interactions
- Ensure relationship source_targets cover your defined entity types

### 3. Attribute Design

- 1-3 key attributes per entity type
- **Note**: Attribute names cannot use `name`, `uuid`, `group_id`, `created_at`, `summary` (these are system reserved words)
- Recommended: `full_name`, `title`, `role`, `position`, `location`, `description`, etc.

## Entity Type Reference

**Individual types (specific)**:
- Student: Student
- Professor: Professor/Scholar
- Journalist: Journalist
- Celebrity: Celebrity/Internet celebrity
- Executive: Executive
- Official: Government official
- Lawyer: Lawyer
- Doctor: Doctor

**Individual types (fallback)**:
- Person: Any natural person (use when not fitting other specific types)

**Organization types (specific)**:
- University: University
- Company: Company/Enterprise
- GovernmentAgency: Government agency
- MediaOutlet: Media institution
- Hospital: Hospital
- School: Primary/Secondary school
- NGO: Non-governmental organization

**Organization types (fallback)**:
- Organization: Any organization (use when not fitting other specific types)

## Relationship Type Reference

- WORKS_FOR: Works for
- STUDIES_AT: Studies at
- AFFILIATED_WITH: Affiliated with
- REPRESENTS: Represents
- REGULATES: Regulates
- REPORTS_ON: Reports on
- COMMENTS_ON: Comments on
- RESPONDS_TO: Responds to
- SUPPORTS: Supports
- OPPOSES: Opposes
- COLLABORATES_WITH: Collaborates with
- COMPETES_WITH: Competes with
"""


class OntologyGenerator:
    """
    Ontology generator
    Analyze text content and generate entity and relationship type definitions
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate ontology definition

        Args:
            document_texts: List of document texts
            simulation_requirement: Description of simulation requirements
            additional_context: Additional context

        Returns:
            Ontology definition (entity_types, edge_types, etc.)
        """
        # Build user message
        user_message = self._build_user_message(
            document_texts,
            simulation_requirement,
            additional_context
        )

        messages = [
            {"role": "system", "content": ONTOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]

        # Call LLM
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )

        # Validate and post-process
        result = self._validate_and_process(result)

        return result

    # Maximum text length for LLM (50,000 characters)
    MAX_TEXT_LENGTH_FOR_LLM = 50000

    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """Build user message"""

        # Combine texts
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)

        # If text exceeds 50,000 characters, truncate (only affects LLM input, not graph construction)
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(Original text has {original_length} characters, first {self.MAX_TEXT_LENGTH_FOR_LLM} characters extracted for ontology analysis)..."

        message = f"""## Simulation Requirements

{simulation_requirement}

## Document Content

{combined_text}
"""

        if additional_context:
            message += f"""
## Additional Explanation

{additional_context}
"""

        message += """
Based on the above content, design entity types and relationship types suitable for social opinion simulation.

**Rules to follow**:
1. Must output exactly 10 entity types
2. Last 2 must be fallback types: Person (individual fallback) and Organization (organization fallback)
3. First 8 are specific types designed based on text content
4. All entity types must be real-world subjects that can voice opinions, not abstract concepts
5. Attribute names cannot use reserved words like name, uuid, group_id, use full_name, org_name, etc. instead
"""

        return message
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and post-process result"""

        # Ensure necessary fields exist
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""

        # Filter out malformed entity types (missing 'name' key)
        result["entity_types"] = [e for e in result["entity_types"] if "name" in e]

        # Validate entity types
        for entity in result["entity_types"]:
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # Ensure description doesn't exceed 100 characters
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."

        # Filter out malformed edge types (missing 'name' key)
        result["edge_types"] = [e for e in result["edge_types"] if "name" in e]

        # Validate relationship types
        for edge in result["edge_types"]:
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."

        # Zep API limit: maximum 10 custom entity types, maximum 10 custom edge types
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10

        # Fallback type definitions
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }

        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }

        # Check if fallback types already exist
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names

        # Fallback types to add
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)

        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)

            # If adding would exceed 10, need to remove some existing types
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # Calculate how many to remove
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # Remove from end (keep more important specific types in front)
                result["entity_types"] = result["entity_types"][:-to_remove]

            # Add fallback types
            result["entity_types"].extend(fallbacks_to_add)

        # Final check to ensure limits not exceeded (defensive programming)
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]

        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]

        return result
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        [DEPRECATED] Convert ontology definition to Zep-format Pydantic code.
        Not used in MiroFish-Offline (ontology stored as JSON in Neo4j).
        Kept for reference only.
        """
        code_lines = [
            '"""',
            'Custom entity type definitions',
            'Auto-generated by MiroFish for social opinion simulation',
            '"""',
            '',
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
            '',
            '# ============== Entity Type Definitions ==============',
            '',
        ]

        # Generate entity types
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")

            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')

            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')

            code_lines.append('')
            code_lines.append('')

        code_lines.append('# ============== Relationship Type Definitions ==============')
        code_lines.append('')

        # Generate relationship types
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # Convert to PascalCase class name
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")

            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')

            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')

            code_lines.append('')
            code_lines.append('')

        # Generate type dictionaries
        code_lines.append('# ============== Type Configuration ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')

        # Generate source_targets mapping for edges
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')

        return '\n'.join(code_lines)

