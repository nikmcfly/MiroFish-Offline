<template>
  <div class="main-view">
    <!-- Kopfzeile -->
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
            {{ { graph: 'Graph', split: 'Geteilt', workbench: 'Arbeitsbereich' }[mode] }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <div class="workflow-step">
          <span class="step-num">Schritt 2/5</span>
          <span class="step-name">Umgebungs-Setup</span>
        </div>
        <div class="step-divider"></div>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
      </div>
    </header>

    <!-- Hauptinhaltsbereich -->
    <main class="content-area">
      <!-- Linkes Panel: Graph -->
      <div class="panel-wrapper left" :style="leftPanelStyle">
        <GraphPanel 
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="2"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>

      <!-- Rechtes Panel: Schritt 2 Umgebungs-Setup -->
      <div class="panel-wrapper right" :style="rightPanelStyle">
        <Step2EnvSetup
          :simulationId="currentSimulationId"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
          @update-status="updateStatus"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '../components/GraphPanel.vue'
import Step2EnvSetup from '../components/Step2EnvSetup.vue'
import { getProject, getGraphData } from '../api/graph'
import { getSimulation, stopSimulation, getEnvStatus, closeSimulationEnv } from '../api/simulation'

const route = useRoute()
const router = useRouter()

const props = defineProps({
  simulationId: String
})

const viewMode = ref('split')

const currentSimulationId = ref(route.params.simulationId)
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const systemLogs = ref([])
const currentStatus = ref('processing') // processing | completed | error

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

const statusClass = computed(() => currentStatus.value)

const statusText = computed(() => {
  if (currentStatus.value === 'error') return 'Fehler'
  if (currentStatus.value === 'completed') return 'Bereit'
  return 'Wird vorbereitet'
})

const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('de-DE', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 100) systemLogs.value.shift()
}

const updateStatus = (status) => {
  currentStatus.value = status
}

const toggleMaximize = (target) => {
  viewMode.value = viewMode.value === target ? 'split' : target
}

const handleGoBack = () => {
  if (projectData.value?.project_id) {
    router.push({ name: 'Process', params: { projectId: projectData.value.project_id } })
  } else {
    router.push('/')
  }
}

const handleNextStep = (params = {}) => {
  addLog('Schritt 3 wird gestartet: Simulation')
  if (params.maxRounds) {
    addLog(`Benutzerdefinierte Simulationsrunden: ${params.maxRounds}`)
  } else {
    addLog('Automatisch konfigurierte Simulationsrunden werden verwendet')
  }
  const routeParams = {
    name: 'SimulationRun',
    params: { simulationId: currentSimulationId.value }
  }
  if (params.maxRounds) routeParams.query = { maxRounds: params.maxRounds }
  router.push(routeParams)
}

const checkAndStopRunningSimulation = async () => {
  if (!currentSimulationId.value) return
  try {
    const envStatusRes = await getEnvStatus({ simulation_id: currentSimulationId.value })
    if (envStatusRes.success && envStatusRes.data?.env_alive) {
      addLog('Simulationsumgebung läuft, wird beendet...')
      try {
        const closeRes = await closeSimulationEnv({ simulation_id: currentSimulationId.value, timeout: 10 })
        if (closeRes.success) {
          addLog('✓ Simulationsumgebung geschlossen')
        } else {
          addLog(`Schließen fehlgeschlagen: ${closeRes.error || 'Unbekannter Fehler'}`)
          await forceStopSimulation()
        }
      } catch (closeErr) {
        addLog(`Fehler beim Schließen: ${closeErr.message}`)
        await forceStopSimulation()
      }
    } else {
      const simRes = await getSimulation(currentSimulationId.value)
      if (simRes.success && simRes.data?.status === 'running') {
        addLog('Simulation läuft, wird gestoppt...')
        await forceStopSimulation()
      }
    }
  } catch (err) {
    console.warn('Simulationsstatus konnte nicht geprüft werden:', err)
  }
}

const forceStopSimulation = async () => {
  try {
    const stopRes = await stopSimulation({ simulation_id: currentSimulationId.value })
    if (stopRes.success) {
      addLog('✓ Simulation zwangsweise gestoppt')
    } else {
      addLog(`Stopp fehlgeschlagen: ${stopRes.error || 'Unbekannter Fehler'}`)
    }
  } catch (err) {
    addLog(`Stopp-Fehler: ${err.message}`)
  }
}

const loadSimulationData = async () => {
  try {
    addLog(`Simulationsdaten werden geladen: ${currentSimulationId.value}`)
    const simRes = await getSimulation(currentSimulationId.value)
    if (simRes.success && simRes.data) {
      const simData = simRes.data
      if (simData.project_id) {
        const projRes = await getProject(simData.project_id)
        if (projRes.success && projRes.data) {
          projectData.value = projRes.data
          addLog(`Projekt geladen: ${projRes.data.project_id}`)
          if (projRes.data.graph_id) await loadGraph(projRes.data.graph_id)
        }
      }
    } else {
      addLog(`Fehler beim Laden der Simulationsdaten: ${simRes.error || 'Unbekannter Fehler'}`)
    }
  } catch (err) {
    addLog(`Ladefehler: ${err.message}`)
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog('Graphdaten erfolgreich geladen')
    }
  } catch (err) {
    addLog(`Graphladen fehlgeschlagen: ${err.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) loadGraph(projectData.value.graph_id)
}

onMounted(async () => {
  addLog('SimulationView initialisiert')
  await checkAndStopRunningSimulation()
  loadSimulationData()
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
.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 1px;
  cursor: pointer;
}
.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
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
.step-name { font-weight: 700; color: #000; }
.step-divider { width: 1px; height: 14px; background-color: #E0E0E0; }
.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #666;
  font-weight: 500;
}
.dot { width: 8px; height: 8px; border-radius: 50%; background: #CCC; }
.status-indicator.processing .dot { background: #FF5722; animation: pulse 1s infinite; }
.status-indicator.completed .dot { background: #4CAF50; }
.status-indicator.error .dot { background: #F44336; }
@keyframes pulse { 50% { opacity: 0.5; } }
.content-area { flex: 1; display: flex; position: relative; overflow: hidden; }
.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), opacity 0.3s ease, transform 0.3s ease;
  will-change: width, opacity, transform;
}
.panel-wrapper.left { border-right: 1px solid #EAEAEA; }
</style>
