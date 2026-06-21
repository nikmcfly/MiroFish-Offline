/**
 * Temporarily store files and requirements to be uploaded
 * Used to immediately navigate after clicking Start Engine on home page, API call is made on Process page
 *
 * Persists to sessionStorage so uploads survive page refreshes within the same browser tab.
 */

const STORAGE_KEY = 'mirofish_pending_upload'

// In-memory reactive state (single source of truth)
const state = {
  files: [],
  simulationRequirement: '',
  isPending: false
}

/**
 * Save current state to sessionStorage.
 * Note: File objects cannot be serialized, so we only persist the requirement and a flag.
 * On restore, the user will need to re-select files — but the requirement text is preserved.
 */
function _saveToStorage() {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      simulationRequirement: state.simulationRequirement,
      isPending: state.isPending,
      fileCount: state.files.length,
      fileNames: state.files.map(f => f.name),
      savedAt: Date.now()
    }))
  } catch (e) {
    // sessionStorage may be full or unavailable — non-critical
    console.warn('Could not save to sessionStorage:', e)
  }
}

/**
 * Load state from sessionStorage on initialization.
 */
function _loadFromStorage() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (raw) {
      const saved = JSON.parse(raw)
      // Only restore if saved recently (within 30 minutes)
      const age = Date.now() - (saved.savedAt || 0)
      if (age < 30 * 60 * 1000) {
        state.simulationRequirement = saved.simulationRequirement || ''
        state.isPending = saved.isPending || false
        // Files can't be restored from sessionStorage (File objects aren't serializable)
        // If isPending was true but files are gone, clear the flag
        if (state.isPending && saved.fileCount > 0) {
          // Mark that files were lost — the UI can check and show a message
          state._filesLost = true
        }
      } else {
        // Expired — clear it
        sessionStorage.removeItem(STORAGE_KEY)
      }
    }
  } catch (e) {
    console.warn('Could not load from sessionStorage:', e)
  }
}

// Restore on module load
_loadFromStorage()

export function setPendingUpload(files, requirement) {
  state.files = files
  state.simulationRequirement = requirement
  state.isPending = true
  state._filesLost = false
  _saveToStorage()
}

export function getPendingUpload() {
  return {
    files: state.files,
    simulationRequirement: state.simulationRequirement,
    isPending: state.isPending,
    filesLost: state._filesLost || false
  }
}

export function clearPendingUpload() {
  state.files = []
  state.simulationRequirement = ''
  state.isPending = false
  state._filesLost = false
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch (e) {
    // Ignore
  }
}

export default state
