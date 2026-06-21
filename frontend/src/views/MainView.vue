<template>
  <div class="main-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">MIROFISH OFFLINE</div>
      </div>
      
      <div class="header-center">
        <div class="view-switcher">
          <button 
            v-for="mode in ['graph', 'split', 'workbench']" 
            :key="mode"
            class="switch-btn"
            :class="{ active: viewMode === mode }"
            @click="viewMode = mode"
          >
            {{ { graph: 'Graph', split: 'Split', workbench: 'Workbench' }[mode] }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <div class="workflow-step">
          <span class="step-num">Step {{ currentStep }}/5</span>
          <span class="step-name">{{ stepNames[currentStep - 1] }}</span>
        </div>
        <div class="step-divider"></div>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
        <div class="step-divider"></div>
        <span class="connection-indicator" :class="connectedClass" :title="connectedTitle">
          <span class="conn-dot"></span>
          {{ connectedText }}
        </span>
      </div>
    </header>

    <!-- Main Content Area -->
    <main class="content-area">
      <!-- Left Panel: Graph -->
      <div class="panel-wrapper left" :style="leftPanelStyle">
        <GraphPanel 
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="currentPhase"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>

      <!-- Right Panel: Step Components -->
      <div class="panel-wrapper right" :style="rightPanelStyle">
        <!-- Step 1: Graph Build -->
        <Step1GraphBuild
          v-if="currentStep === 1"
          :currentPhase="currentPhase"
          :projectData="projectData"
          :ontologyProgress="ontologyProgress"
          :buildProgress="buildProgress"
          :graphData="graphData"
          :systemLogs="systemLogs"
          :rebuilding="rebuilding"
          @next-step="handleNextStep"
          @rebuild="handleRebuildGraph"
        />
        <!-- Step 2: Env Setup -->
        <Step2EnvSetup
          v-else-if="currentStep === 2"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '../components/GraphPanel.vue'
import Step1GraphBuild from '../components/Step1GraphBuild.vue'
import Step2EnvSetup from '../components/Step2EnvSetup.vue'
import { generateOntology, getProject, buildGraph, getTaskStatus, getGraphData } from '../api/graph'
import { getPendingUpload, clearPendingUpload } from '../store/pendingUpload'

const route = useRoute()
const router = useRouter()

// Layout State
const viewMode = ref('split') // graph | split | workbench

// Step State
const currentStep = ref(1) // 1: Graph Build, 2: Env Setup, 3: Simulation, 4: Report, 5: Interaction
const stepNames = ['Graph Build', 'Env Setup', 'Simulation', 'Report', 'Interaction']

// Data State
const currentProjectId = ref(route.params.projectId)
const loading = ref(false)
const graphLoading = ref(false)
const error = ref('')
const projectData = ref(null)
const graphData = ref(null)
const currentPhase = ref(-1) // -1: Upload, 0: Ontology, 1: Build, 2: Complete
const ontologyProgress = ref(null)
const buildProgress = ref(null)
const systemLogs = ref([])
const rebuilding = ref(false)

// Polling timeout and error tracking
const MAX_POLL_DURATION = 30 * 60 * 1000  // 30 minutes
const MAX_CONSECUTIVE_ERRORS = 10
let pollStartTime = null
let consecutivePollErrors = 0

// Polling timers
let pollTimer = null
let graphPollTimer = null

// --- Computed Layout Styles ---
const leftPanelStyle = computed(() => {
  if (viewMode.value === 'graph') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'workbench') return { width: '0%', opacity: 0, transform: 'translateX(-20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

const rightPanelStyle = computed(() => {
  if (viewMode.value === 'workbench') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'graph') return { width: '0%', opacity: 0, transform: 'translateX(20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

// --- Status Computed ---
const statusClass = computed(() => {
  if (error.value) return 'error'
  if (currentPhase.value >= 2) return 'completed'
  return 'processing'
})

const statusText = computed(() => {
  if (error.value) return 'Error'
  if (currentPhase.value >= 2) return 'Ready'
  if (currentPhase.value === 1) return 'Building Graph'
  if (currentPhase.value === 0) return 'Generating Ontology'
  return 'Initializing'
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  // Keep last 100 logs
  if (systemLogs.value.length > 100) {
    systemLogs.value.shift()
  }
}

// --- Connection Status ---
const backendReachable = ref(true)
let connectionCheckTimer = null

const checkBackendHealth = async () => {
  try {
    const res = await getProject(currentProjectId.value || 'nonexistent')
    // Any response (even 404) means backend is reachable
    backendReachable.value = true
  } catch (e) {
    if (backendReachable.value) {
      addLog('WARNING: Backend unreachable — check if server is running')
    }
    backendReachable.value = false
  }
}

const connectedClass = computed(() => backendReachable.value ? 'ok' : 'down')
const connectedText = computed(() => backendReachable.value ? 'Connected' : 'Offline')
const connectedTitle = computed(() => backendReachable.value
  ? 'Backend connection OK'
  : 'Backend unreachable — API calls will fail')

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

const handleNextStep = (params = {}) => {
  if (currentStep.value < 5) {
    currentStep.value++
    addLog(`Entering Step ${currentStep.value}: ${stepNames[currentStep.value - 1]}`)

    // If entering Step 3 from Step 2, log simulation round config
    if (currentStep.value === 3 && params.maxRounds) {
      addLog(`Custom simulation rounds: ${params.maxRounds}`)
    }
  }
}

const handleGoBack = () => {
  if (currentStep.value > 1) {
    currentStep.value--
    addLog(`Back to Step ${currentStep.value}: ${stepNames[currentStep.value - 1]}`)
  }
}

// --- Data Logic ---

const initProject = async () => {
  addLog('Project view initialized.')
  if (currentProjectId.value === 'new') {
    await handleNewProject()
  } else {
    await loadProject()
  }
}

const handleNewProject = async () => {
  const pending = getPendingUpload()
  if (!pending.isPending || pending.files.length === 0) {
    if (pending.filesLost) {
      error.value = 'Uploaded files were lost due to a page refresh. Please go back and re-upload your files.'
      addLog('Error: Files lost on refresh. Please re-upload from the home page.')
    } else {
      error.value = 'No pending files found.'
      addLog('Error: No pending files found for new project.')
    }
    return
  }
  
  try {
    loading.value = true
    currentPhase.value = 0
    ontologyProgress.value = { message: 'Uploading and analyzing docs...' }
    addLog('Starting ontology generation: Uploading files...')
    
    const formData = new FormData()
    pending.files.forEach(f => formData.append('files', f))
    formData.append('simulation_requirement', pending.simulationRequirement)
    
    const res = await generateOntology(formData)
    if (res.success) {
      clearPendingUpload()
      currentProjectId.value = res.data.project_id
      projectData.value = res.data
      
      router.replace({ name: 'Process', params: { projectId: res.data.project_id } })
      ontologyProgress.value = null
      addLog(`Ontology generated successfully for project ${res.data.project_id}`)
      await startBuildGraph()
    } else {
      error.value = res.error || 'Ontology generation failed'
      addLog(`Error generating ontology: ${error.value}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in handleNewProject: ${err.message}`)
  } finally {
    loading.value = false
  }
}

const loadProject = async () => {
  try {
    loading.value = true
    addLog(`Loading project ${currentProjectId.value}...`)
    const res = await getProject(currentProjectId.value)
    if (res.success) {
      projectData.value = res.data
      updatePhaseByStatus(res.data.status)
      addLog(`Project loaded. Status: ${res.data.status}`)
      
      if (res.data.status === 'ontology_generated' && !res.data.graph_id) {
        await startBuildGraph()
      } else if (res.data.status === 'graph_building' && res.data.graph_build_task_id) {
        currentPhase.value = 1
        startPollingTask(res.data.graph_build_task_id)
        startGraphPolling()
      } else if (res.data.status === 'graph_completed' && res.data.graph_id) {
        currentPhase.value = 2
        await loadGraph(res.data.graph_id)
      }
    } else {
      error.value = res.error
      addLog(`Error loading project: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in loadProject: ${err.message}`)
  } finally {
    loading.value = false
  }
}

const updatePhaseByStatus = (status) => {
  switch (status) {
    case 'created':
    case 'ontology_generated': currentPhase.value = 0; break;
    case 'graph_building': currentPhase.value = 1; break;
    case 'graph_completed': currentPhase.value = 2; break;
    case 'failed': error.value = 'Project failed'; break;
  }
}

const startBuildGraph = async () => {
  try {
    currentPhase.value = 1
    buildProgress.value = { progress: 0, message: 'Starting build...' }
    addLog('Initiating graph build...')

    const res = await buildGraph({ project_id: currentProjectId.value })
    if (res.success) {
      addLog(`Graph build task started. Task ID: ${res.data.task_id}`)
      startGraphPolling()
      startPollingTask(res.data.task_id)
    } else {
      error.value = res.error
      addLog(`Error starting build: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in startBuildGraph: ${err.message}`)
  }
}

const handleRebuildGraph = async () => {
  if (!currentProjectId.value || rebuilding.value) return
  try {
    rebuilding.value = true
    currentPhase.value = 1
    graphData.value = null
    buildProgress.value = { progress: 0, message: 'Rebuilding graph...' }
    error.value = ''
    addLog('Rebuilding graph with force=true...')

    const res = await buildGraph({ project_id: currentProjectId.value, force: true })
    if (res.success) {
      addLog(`Rebuild task started. Task ID: ${res.data.task_id}`)
      startGraphPolling()
      startPollingTask(res.data.task_id)
    } else {
      error.value = res.error
      addLog(`Error starting rebuild: ${res.error}`)
      currentPhase.value = 2
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in rebuild: ${err.message}`)
    currentPhase.value = 2
  } finally {
    rebuilding.value = false
  }
}

const startGraphPolling = () => {
  addLog('Started polling for graph data...')
  fetchGraphData()
  graphPollTimer = setInterval(fetchGraphData, 10000)
}

const fetchGraphData = async () => {
  try {
    // Refresh project info to check for graph_id
    const projRes = await getProject(currentProjectId.value)
    if (projRes.success && projRes.data.graph_id) {
      const gRes = await getGraphData(projRes.data.graph_id)
      if (gRes.success) {
        graphData.value = gRes.data
        const nodeCount = gRes.data.node_count || gRes.data.nodes?.length || 0
        const edgeCount = gRes.data.edge_count || gRes.data.edges?.length || 0
        addLog(`Graph data refreshed. Nodes: ${nodeCount}, Edges: ${edgeCount}`)
      }
    }
  } catch (err) {
    console.warn('Graph fetch error:', err)
  }
}

const startPollingTask = (taskId) => {
  pollStartTime = Date.now()
  consecutivePollErrors = 0
  pollTaskStatus(taskId)
  pollTimer = setInterval(() => pollTaskStatus(taskId), 2000)
}

const pollTaskStatus = async (taskId) => {
  // Check timeout
  if (pollStartTime && (Date.now() - pollStartTime > MAX_POLL_DURATION)) {
    stopPolling()
    stopGraphPolling()
    addLog('WARNING: Polling timed out after 30 minutes. The build may still be running in the backend. Try refreshing.')
    buildProgress.value = { progress: buildProgress.value?.progress || 0, message: 'Polling timed out — check backend logs' }
    return
  }

  try {
    const res = await getTaskStatus(taskId)
    consecutivePollErrors = 0  // Reset on success

    if (res.success) {
      const task = res.data

      // Log progress message if it changed
      if (task.message && task.message !== buildProgress.value?.message) {
        addLog(task.message)
      }

      buildProgress.value = { progress: task.progress || 0, message: task.message }

      if (task.status === 'completed') {
        addLog('Graph build task completed.')
        stopPolling()
        stopGraphPolling()
        currentPhase.value = 2

        const projRes = await getProject(currentProjectId.value)
        if (projRes.success && projRes.data.graph_id) {
            projectData.value = projRes.data
            await loadGraph(projRes.data.graph_id)
            const nodeCount = graphData.value?.node_count || graphData.value?.nodes?.length || 0
            if (nodeCount > 0) {
              addLog(`Graph loaded: ${nodeCount} entities.`)
            } else {
              addLog('WARNING: Graph build completed but 0 entities found. Use Rebuild to retry.')
            }
        }
      } else if (task.status === 'failed') {
        stopPolling()
        stopGraphPolling()
        currentPhase.value = 2
        addLog(`Graph build FAILED: ${task.error || task.message || 'Unknown error'}`)

        const projRes = await getProject(currentProjectId.value)
        if (projRes.success && projRes.data.graph_id) {
          projectData.value = projRes.data
          await loadGraph(projRes.data.graph_id)
        }
      }
    }
  } catch (e) {
    consecutivePollErrors++
    if (consecutivePollErrors >= MAX_CONSECUTIVE_ERRORS) {
      stopPolling()
      stopGraphPolling()
      addLog(`ERROR: Lost connection to backend after ${MAX_CONSECUTIVE_ERRORS} failed attempts. The backend may have restarted.`)
      buildProgress.value = { progress: buildProgress.value?.progress || 0, message: 'Backend unreachable — try refreshing or rebuilding' }
    } else if (consecutivePollErrors <= 3) {
      addLog(`Connection issue (attempt ${consecutivePollErrors})...`)
    }
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  addLog(`Loading full graph data: ${graphId}`)
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog('Graph data loaded successfully.')
    } else {
      addLog(`Failed to load graph data: ${res.error}`)
    }
  } catch (e) {
    addLog(`Exception loading graph: ${e.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    addLog('Manual graph refresh triggered.')
    loadGraph(projectData.value.graph_id)
  }
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const stopGraphPolling = () => {
  if (graphPollTimer) {
    clearInterval(graphPollTimer)
    graphPollTimer = null
    addLog('Graph polling stopped.')
  }
}

onMounted(() => {
  initProject()
  // Check backend health every 15 seconds
  checkBackendHealth()
  connectionCheckTimer = setInterval(checkBackendHealth, 15000)
})

onUnmounted(() => {
  stopPolling()
  stopGraphPolling()
  if (connectionCheckTimer) {
    clearInterval(connectionCheckTimer)
    connectionCheckTimer = null
  }
})
</script>

<style scoped>
.main-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #FFF;
  overflow: hidden;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

/* Header */
.app-header {
  height: 60px;
  border-bottom: 1px solid #EAEAEA;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #FFF;
  z-index: 100;
  position: relative;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 1px;
  cursor: pointer;
}

.view-switcher {
  display: flex;
  background: #F5F5F5;
  padding: 4px;
  border-radius: 6px;
  gap: 4px;
}

.switch-btn {
  border: none;
  background: transparent;
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.switch-btn.active {
  background: #FFF;
  color: #000;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #999;
}

.step-name {
  font-weight: 700;
  color: #000;
}

.step-divider {
  width: 1px;
  height: 14px;
  background-color: #E0E0E0;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #CCC;
}

.status-indicator.processing .dot { background: #FF5722; animation: pulse 1s infinite; }
.status-indicator.completed .dot { background: #4CAF50; }
.status-indicator.error .dot { background: #F44336; }

.connection-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 500;
  color: #999;
  cursor: default;
}

.conn-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.connection-indicator.ok .conn-dot { background: #4CAF50; }
.connection-indicator.ok { color: #4CAF50; }
.connection-indicator.down .conn-dot { background: #F44336; animation: pulse 1s infinite; }
.connection-indicator.down { color: #F44336; }

@keyframes pulse { 50% { opacity: 0.5; } }

/* Content */
.content-area {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), opacity 0.3s ease, transform 0.3s ease;
  will-change: width, opacity, transform;
}

.panel-wrapper.left {
  border-right: 1px solid #EAEAEA;
}
</style>
