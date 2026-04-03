<template>
  <div class="dashboard-container">
    <nav class="dash-navbar">
      <div class="dash-nav-brand" @click="$router.push('/')">MIROFISH OFFLINE</div>
      <div class="dash-nav-links">
        <router-link to="/" class="dash-nav-link">Home</router-link>
        <router-link to="/dashboard" class="dash-nav-link active">Dashboard</router-link>
      </div>
    </nav>

    <div class="dash-content">
      <!-- Active Now Section -->
      <section class="dash-section">
        <div class="dash-section-header">
          <span class="dash-section-dot">&#9632;</span>
          <span class="dash-section-label">Active Now</span>
          <span v-if="activeSimulations.length > 0" class="dash-active-count">{{ activeSimulations.length }}</span>
        </div>

        <div v-if="activeSimulations.length > 0" class="active-cards">
          <div v-for="sim in activeSimulations" :key="sim.simulation_id" class="active-card">
            <div class="active-card-header">
              <span class="active-id">{{ formatId(sim.simulation_id) }}</span>
              <span class="status-pill running">
                <span class="pulse-dot"></span> Running
              </span>
            </div>

            <div class="active-requirement">{{ truncate(sim.simulation_requirement, 60) || 'No description' }}</div>

            <div class="active-platforms">
              <span class="platform-tag">Twitter</span>
              <span class="platform-tag">Reddit</span>
            </div>

            <div class="progress-section">
              <div class="progress-label">
                <span>Round {{ sim.current_round || 0 }} / {{ sim.total_rounds || '?' }}</span>
                <span class="progress-pct">{{ getProgress(sim) }}%</span>
              </div>
              <div class="progress-track">
                <div class="progress-fill" :style="{ width: getProgress(sim) + '%' }"></div>
              </div>
            </div>

            <div class="active-meta">
              <span class="meta-item">{{ sim.entities_count || 0 }} agents</span>
              <span class="meta-sep">|</span>
              <span class="meta-item">{{ formatDateShort(sim.created_at) }}</span>
            </div>

            <div class="active-actions">
              <button class="action-btn view-btn" @click="goToSimRun(sim)">View</button>
              <button class="action-btn stop-btn" @click="handleStop(sim)">Stop</button>
            </div>
          </div>
        </div>

        <div v-else class="empty-active">
          <span class="empty-icon">&#9671;</span>
          <span class="empty-text">No active simulations</span>
          <router-link to="/" class="start-link">Start one &rarr;</router-link>
        </div>
      </section>

      <!-- All Simulations Section -->
      <section class="dash-section">
        <div class="dash-section-header">
          <span class="dash-section-dot">&#9671;</span>
          <span class="dash-section-label">All Simulations</span>
          <span class="dash-total-count">{{ filteredSimulations.length }}</span>
        </div>

        <div class="filter-bar">
          <input
            v-model="searchQuery"
            class="filter-input"
            type="text"
            placeholder="Search by ID or requirement..."
          />
          <div class="filter-tabs">
            <button
              v-for="tab in statusTabs"
              :key="tab.value"
              class="filter-tab"
              :class="{ active: activeTab === tab.value }"
              @click="activeTab = tab.value"
            >{{ tab.label }}</button>
          </div>
        </div>

        <div v-if="loading && allSimulations.length === 0" class="table-loading">Loading...</div>

        <div v-else-if="filteredSimulations.length === 0" class="table-empty">
          No simulations found
        </div>

        <div v-else class="sim-table-wrap">
          <table class="sim-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Requirement</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Agents</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="sim in filteredSimulations" :key="sim.simulation_id">
                <td class="cell-id">{{ formatId(sim.simulation_id) }}</td>
                <td class="cell-req">{{ truncate(sim.simulation_requirement, 50) || '---' }}</td>
                <td>
                  <span class="status-pill" :class="getStatusClass(sim)">
                    <span class="status-dot-sm">&#9679;</span> {{ getStatusLabel(sim) }}
                  </span>
                </td>
                <td class="cell-progress">
                  <span class="progress-text">{{ sim.current_round || 0 }}/{{ sim.total_rounds || '?' }}</span>
                  <div class="mini-progress-track">
                    <div class="mini-progress-fill" :style="{ width: getProgress(sim) + '%' }"></div>
                  </div>
                </td>
                <td class="cell-num">{{ sim.entities_count || 0 }}</td>
                <td class="cell-date">{{ formatDateShort(sim.created_at) }}</td>
                <td class="cell-actions">
                  <button
                    v-if="sim.project_id"
                    class="tbl-btn"
                    title="Graph"
                    @click="$router.push({ name: 'Process', params: { projectId: sim.project_id } })"
                  >&#9671;</button>
                  <button
                    class="tbl-btn"
                    title="Simulation"
                    @click="goToSimRun(sim)"
                  >&#9672;</button>
                  <button
                    v-if="sim.report_id"
                    class="tbl-btn"
                    title="Report"
                    @click="$router.push({ name: 'Report', params: { reportId: sim.report_id } })"
                  >&#9670;</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { getSimulationHistory, stopSimulation } from '../api/simulation'

const router = useRouter()

const allSimulations = ref([])
const loading = ref(true)
const searchQuery = ref('')
const activeTab = ref('all')
let pollTimer = null

const statusTabs = [
  { label: 'All', value: 'all' },
  { label: 'Running', value: 'running' },
  { label: 'Completed', value: 'completed' },
  { label: 'Stopped', value: 'stopped' },
]

const activeSimulations = computed(() =>
  allSimulations.value.filter(s => s.runner_status === 'running')
)

const filteredSimulations = computed(() => {
  let list = allSimulations.value

  if (activeTab.value !== 'all') {
    list = list.filter(s => getStatusKey(s) === activeTab.value)
  }

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(s =>
      (s.simulation_id || '').toLowerCase().includes(q) ||
      (s.simulation_requirement || '').toLowerCase().includes(q)
    )
  }

  return list
})

function getStatusKey(sim) {
  if (sim.runner_status === 'running') return 'running'
  if (sim.runner_status === 'completed' || sim.status === 'completed') return 'completed'
  if (sim.runner_status === 'stopped') return 'stopped'
  return 'idle'
}

function getStatusLabel(sim) {
  const key = getStatusKey(sim)
  return key.charAt(0).toUpperCase() + key.slice(1)
}

function getStatusClass(sim) {
  return getStatusKey(sim)
}

function getProgress(sim) {
  if (!sim.total_rounds || sim.total_rounds === 0) return 0
  return Math.min(100, Math.round(((sim.current_round || 0) / sim.total_rounds) * 100))
}

function formatId(id) {
  if (!id) return '---'
  return id.length > 12 ? id.slice(0, 12) + '...' : id
}

function truncate(text, max) {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

function formatDateShort(dateStr) {
  if (!dateStr) return '---'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return dateStr.slice(0, 10)
  }
}

function goToSimRun(sim) {
  router.push({ name: 'SimulationRun', params: { simulationId: sim.simulation_id } })
}

async function fetchData() {
  try {
    const res = await getSimulationHistory(50)
    if (res.success && res.data) {
      allSimulations.value = res.data
    }
  } catch (e) {
    console.error('Failed to fetch simulations:', e)
  } finally {
    loading.value = false
  }
}

async function handleStop(sim) {
  if (!confirm(`Stop simulation ${formatId(sim.simulation_id)}?`)) return
  try {
    await stopSimulation({ simulation_id: sim.simulation_id })
    await fetchData()
  } catch (e) {
    console.error('Failed to stop simulation:', e)
  }
}

onMounted(() => {
  fetchData()
  pollTimer = setInterval(fetchData, 3000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.dashboard-container {
  min-height: 100vh;
  background: #fff;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  color: #111;
}

/* Navbar */
.dash-navbar {
  height: 60px;
  background: #000;
  color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
}
.dash-nav-brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.2rem;
  cursor: pointer;
}
.dash-nav-links {
  display: flex;
  gap: 24px;
}
.dash-nav-link {
  color: #888;
  text-decoration: none;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  font-weight: 500;
  transition: color 0.2s;
}
.dash-nav-link:hover,
.dash-nav-link.active {
  color: #fff;
}

/* Content */
.dash-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 40px 40px 80px;
}

/* Section Headers */
.dash-section {
  margin-bottom: 50px;
}
.dash-section-header {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.dash-section-dot {
  color: #FF4500;
  font-size: 0.8rem;
}
.dash-active-count,
.dash-total-count {
  background: #f0f0f0;
  color: #333;
  padding: 2px 8px;
  font-size: 0.7rem;
  font-weight: 700;
  border-radius: 2px;
}
.dash-active-count {
  background: #FF4500;
  color: #fff;
}

/* Active Cards */
.active-cards {
  display: flex;
  gap: 20px;
  overflow-x: auto;
  padding-bottom: 10px;
}
.active-card {
  min-width: 320px;
  max-width: 380px;
  border: 1px solid #e0e0e0;
  padding: 24px;
  flex-shrink: 0;
  position: relative;
  transition: border-color 0.3s, box-shadow 0.3s;
}
.active-card:hover {
  border-color: #FF4500;
  box-shadow: 0 0 0 1px #FF4500;
}
.active-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.active-id {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #666;
}
.active-requirement {
  font-size: 0.9rem;
  color: #333;
  line-height: 1.5;
  margin-bottom: 12px;
  min-height: 40px;
}
.active-platforms {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.platform-tag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  padding: 3px 8px;
  border: 1px solid #ddd;
  color: #666;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.progress-section {
  margin-bottom: 12px;
}
.progress-label {
  display: flex;
  justify-content: space-between;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #666;
  margin-bottom: 6px;
}
.progress-pct {
  color: #FF4500;
  font-weight: 700;
}
.progress-track {
  height: 4px;
  background: #f0f0f0;
  width: 100%;
}
.progress-fill {
  height: 100%;
  background: #FF4500;
  transition: width 0.5s ease;
}
.active-meta {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: #999;
  margin-bottom: 16px;
  display: flex;
  gap: 6px;
}
.meta-sep {
  color: #ddd;
}
.active-actions {
  display: flex;
  gap: 10px;
}
.action-btn {
  flex: 1;
  padding: 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  border: none;
  letter-spacing: 0.5px;
  transition: opacity 0.2s;
}
.action-btn:hover {
  opacity: 0.85;
}
.view-btn {
  background: #000;
  color: #fff;
}
.stop-btn {
  background: transparent;
  color: #FF4500;
  border: 1px solid #FF4500;
}

/* Status Pills */
.status-pill {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  padding: 3px 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 2px;
  font-weight: 600;
  letter-spacing: 0.3px;
}
.status-pill.running {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}
.status-pill.completed {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}
.status-pill.stopped {
  background: rgba(107, 114, 128, 0.1);
  color: #6b7280;
}
.status-pill.idle {
  background: rgba(107, 114, 128, 0.05);
  color: #9ca3af;
}
.status-dot-sm {
  font-size: 0.5rem;
}
.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #16a34a;
  display: inline-block;
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(22, 163, 106, 0.4); }
  50% { opacity: 0.7; box-shadow: 0 0 0 4px rgba(22, 163, 106, 0); }
}

/* Empty Active */
.empty-active {
  border: 1px dashed #ddd;
  padding: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #999;
}
.empty-icon {
  font-size: 1.5rem;
  color: #ccc;
}
.empty-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}
.start-link {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #FF4500;
  text-decoration: none;
  font-weight: 600;
}
.start-link:hover {
  text-decoration: underline;
}

/* Filter Bar */
.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 16px;
}
.filter-input {
  flex: 1;
  max-width: 400px;
  padding: 10px 14px;
  border: 1px solid #e0e0e0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  outline: none;
  background: #fafafa;
  transition: border-color 0.2s;
}
.filter-input:focus {
  border-color: #999;
}
.filter-input::placeholder {
  color: #bbb;
}
.filter-tabs {
  display: flex;
  gap: 0;
}
.filter-tab {
  padding: 8px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid #e0e0e0;
  background: transparent;
  color: #999;
  transition: all 0.2s;
  margin-left: -1px;
}
.filter-tab:first-child {
  margin-left: 0;
}
.filter-tab.active {
  background: #000;
  color: #fff;
  border-color: #000;
  z-index: 1;
  position: relative;
}
.filter-tab:hover:not(.active) {
  color: #333;
  background: #f5f5f5;
}

/* Table */
.sim-table-wrap {
  border: 1px solid #e0e0e0;
  overflow-x: auto;
}
.sim-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.sim-table thead {
  background: #fafafa;
}
.sim-table th {
  text-align: left;
  padding: 12px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #e0e0e0;
  white-space: nowrap;
}
.sim-table td {
  padding: 14px 16px;
  border-bottom: 1px solid #f0f0f0;
  vertical-align: middle;
}
.sim-table tbody tr:hover {
  background: #fafafa;
}
.sim-table tbody tr:last-child td {
  border-bottom: none;
}
.cell-id {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #666;
  white-space: nowrap;
}
.cell-req {
  color: #333;
  max-width: 300px;
}
.cell-progress {
  white-space: nowrap;
}
.progress-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #666;
  display: block;
  margin-bottom: 4px;
}
.mini-progress-track {
  height: 3px;
  background: #f0f0f0;
  width: 80px;
}
.mini-progress-fill {
  height: 100%;
  background: #FF4500;
  transition: width 0.5s ease;
}
.cell-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #666;
  text-align: center;
}
.cell-date {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #999;
  white-space: nowrap;
}
.cell-actions {
  display: flex;
  gap: 6px;
}
.tbl-btn {
  width: 30px;
  height: 30px;
  border: 1px solid #e0e0e0;
  background: transparent;
  cursor: pointer;
  font-size: 0.9rem;
  color: #999;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.tbl-btn:hover {
  border-color: #000;
  color: #000;
}

.table-loading,
.table-empty {
  padding: 40px;
  text-align: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  color: #999;
  border: 1px solid #e0e0e0;
}
</style>
