<template>
  <div class="backtest-page">
    <!-- ═══════ NAVBAR ═══════ -->
    <nav class="bt-nav">
      <div class="bt-nav-left" @click="$router.push('/')">
        <span class="bt-nav-brand">MIROFISH OFFLINE</span>
      </div>
      <div class="bt-nav-center">
        <div class="bt-nav-links">
          <button class="bt-nav-link" @click="$router.push('/')">Home</button>
          <button class="bt-nav-link" @click="$router.push('/prediction')">Prediction</button>
          <button class="bt-nav-link active" @click="$router.push('/backtest')">Backtest</button>
        </div>
        <span class="paper-badge">PAPER</span>
      </div>
      <div class="bt-nav-right">
        <button class="bt-nav-back" @click="$router.push('/')">
          <span class="back-arrow">←</span> Home
        </button>
      </div>
    </nav>

    <!-- ═══════ HERO STRIP ═══════ -->
    <div class="bt-hero">
      <div class="bt-hero-inner">
        <div class="bt-hero-left">
          <span class="bt-hero-tag">BACKTEST</span>
          <span class="bt-hero-sep">/</span>
          <span class="bt-hero-tag accent">SIGNAL VALIDATION</span>
          <span class="bt-hero-sep">/</span>
          <span class="bt-hero-tag">CALIBRATION</span>
        </div>
        <div class="bt-hero-right">
          <div class="bt-hero-stat">
            <span class="bt-hero-stat-val">{{ backtestRuns.length }}</span>
            <span class="bt-hero-stat-label">Runs</span>
          </div>
          <div class="bt-hero-stat">
            <span class="bt-hero-stat-val">{{ totalMarketsTestedAll }}</span>
            <span class="bt-hero-stat-label">Markets Tested</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════ MAIN CONTENT ═══════ -->
    <div class="bt-main">
      <div class="bt-grid">

        <!-- ══════════════ LEFT PANEL ══════════════ -->
        <div class="bt-col bt-col-left">

          <!-- Run Backtest Panel -->
          <div class="bt-panel">
            <div class="bt-panel-head">
              <div class="bt-panel-title">
                <span class="bt-dot"></span>
                Run Backtest
              </div>
            </div>
            <div class="bt-run-form">
              <div class="bt-form-row">
                <label class="bt-label">Market Count</label>
                <input
                  v-model.number="marketCount"
                  type="number"
                  class="bt-input"
                  min="1"
                  max="500"
                  :disabled="isRunning"
                />
              </div>
              <button
                class="bt-run-btn"
                :class="{ disabled: isRunning }"
                @click="runBacktest"
                :disabled="isRunning"
              >
                <span class="run-btn-label">
                  <span v-if="!isRunning">Start Backtest</span>
                  <span v-else class="running-text">
                    <span class="run-spinner"></span>
                    Running...
                  </span>
                </span>
                <span class="run-btn-arrow" v-if="!isRunning">→</span>
              </button>
            </div>
          </div>

          <!-- Run History Panel -->
          <div class="bt-panel">
            <div class="bt-panel-head">
              <div class="bt-panel-title">
                <span class="bt-dot"></span>
                Run History
              </div>
              <button class="bt-btn-sm" @click="loadBacktests">Refresh</button>
            </div>
            <div class="bt-history">
              <!-- Loading skeleton -->
              <template v-if="loadingHistory && backtestRuns.length === 0">
                <div v-for="i in 4" :key="'skel-'+i" class="bt-skeleton">
                  <div class="skel-line skel-title"></div>
                  <div class="skel-line skel-meta"></div>
                </div>
              </template>

              <div v-if="!loadingHistory && backtestRuns.length === 0" class="bt-empty-mini">
                No backtest runs yet
              </div>

              <div
                v-for="run in backtestRuns"
                :key="run.id"
                class="history-row"
                :class="{ active: activeRunId === run.id }"
                @click="selectRun(run)"
              >
                <div class="history-left">
                  <div class="history-title">{{ run.id.substring(0, 12) }}...</div>
                  <div class="history-date">{{ formatDate(run.started_at) }}</div>
                </div>
                <div class="history-right">
                  <span class="history-status" :class="'status-' + run.status">
                    {{ run.status }}
                  </span>
                  <span v-if="run.status === 'RUNNING' || run.status === 'PENDING'" class="history-progress">
                    {{ run.completed_markets || 0 }}/{{ run.total_markets || '?' }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Paper Trading Panel -->
          <div class="bt-panel">
            <div class="bt-panel-head">
              <div class="bt-panel-title">
                <span class="bt-dot"></span>
                Paper Trading
              </div>
            </div>
            <div class="bt-paper-status">
              <div class="paper-indicator">
                <span class="paper-dot enabled"></span>
                <span class="paper-text">Enabled</span>
              </div>
              <div class="paper-hint">Signals are simulated. No real trades are executed.</div>
            </div>
          </div>
        </div>

        <!-- ══════════════ RIGHT PANEL ══════════════ -->
        <div class="bt-col bt-col-right">

          <!-- Error State -->
          <div v-if="errorMsg" class="bt-panel panel-error">
            <div class="bt-panel-head">
              <div class="bt-panel-title">
                <span class="bt-dot error-dot"></span>
                Error
              </div>
            </div>
            <div class="error-msg">{{ errorMsg }}</div>
          </div>

          <!-- Empty State -->
          <div v-if="!currentRun && !errorMsg && !loadingRun" class="bt-panel">
            <div class="bt-empty-state">
              <div class="empty-icon">◇</div>
              <div class="empty-text">Run a backtest to validate your signal quality</div>
              <div class="empty-hint">Configure market count and click Start Backtest</div>
            </div>
          </div>

          <!-- Loading State -->
          <div v-if="loadingRun && !currentRun" class="bt-panel">
            <div class="bt-skeleton-results">
              <div v-for="i in 5" :key="'rskel-'+i" class="skel-metric-card">
                <div class="skel-line skel-val"></div>
                <div class="skel-line skel-label"></div>
              </div>
            </div>
          </div>

          <!-- In-Progress Badge -->
          <div v-if="currentRun && (currentRun.status === 'RUNNING' || currentRun.status === 'PENDING')" class="bt-progress-badge">
            <span class="progress-pulse"></span>
            IN PROGRESS — {{ currentRun.completed_markets || 0 }}/{{ currentRun.total_markets || '?' }} markets
          </div>

          <!-- Results Panel -->
          <div v-if="currentRun" class="bt-panel">
            <div class="bt-panel-head">
              <div class="bt-panel-title">
                <span class="bt-dot"></span>
                Results
              </div>
              <span v-if="currentRun.status === 'COMPLETED'" class="status-badge completed">COMPLETED</span>
              <span v-else-if="currentRun.status === 'FAILED'" class="status-badge failed">FAILED</span>
            </div>

            <!-- Hero Metrics -->
            <div class="bt-metrics-grid">
              <div class="bt-metric-card">
                <div class="bt-metric-val" :class="roiClass">{{ formatPct(currentRun.metrics?.roi) }}</div>
                <div class="bt-metric-label">ROI</div>
              </div>
              <div class="bt-metric-card">
                <div class="bt-metric-val">{{ formatPct(currentRun.metrics?.accuracy) }}</div>
                <div class="bt-metric-label">Accuracy</div>
              </div>
              <div class="bt-metric-card">
                <div class="bt-metric-val">{{ formatNum(currentRun.metrics?.brier_score) }}</div>
                <div class="bt-metric-label">Brier Score</div>
              </div>
              <div class="bt-metric-card">
                <div class="bt-metric-val">{{ formatNum(currentRun.metrics?.sharpe_ratio) }}</div>
                <div class="bt-metric-label">Sharpe</div>
              </div>
              <div class="bt-metric-card">
                <div class="bt-metric-val">{{ currentRun.metrics?.markets_tested || currentRun.total_markets || 0 }}</div>
                <div class="bt-metric-label">Markets Tested</div>
              </div>
            </div>
          </div>

          <!-- Category Breakdown -->
          <div v-if="currentRun && currentRun.metrics?.category_metrics" class="bt-panel">
            <div class="bt-panel-head">
              <div class="bt-panel-title">
                <span class="bt-dot"></span>
                Category Breakdown
              </div>
            </div>
            <div class="bt-table-wrap">
              <table class="bt-table">
                <thead>
                  <tr>
                    <th>Category</th>
                    <th>Accuracy</th>
                    <th>Brier</th>
                    <th>ROI</th>
                    <th>N</th>
                    <th>Avg Edge</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(metrics, cat) in currentRun.metrics.category_metrics"
                    :key="cat"
                    class="bt-table-row"
                  >
                    <td><span class="category-badge">{{ cat }}</span></td>
                    <td class="col-num">{{ formatPct(metrics.accuracy) }}</td>
                    <td class="col-num">{{ formatNum(metrics.brier_score) }}</td>
                    <td class="col-num" :class="edgeClass(metrics.roi)">{{ formatPct(metrics.roi) }}</td>
                    <td class="col-num">{{ metrics.markets_tested }}</td>
                    <td class="col-num" :class="edgeClass(metrics.avg_edge)">
                      {{ metrics.avg_edge != null ? (metrics.avg_edge >= 0 ? '+' : '') + (metrics.avg_edge * 100).toFixed(1) + '%' : '-' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Confidence Tier Breakdown -->
          <div v-if="currentRun && currentRun.metrics?.confidence_tier_metrics" class="bt-panel">
            <div class="bt-panel-head">
              <div class="bt-panel-title">
                <span class="bt-dot"></span>
                Confidence Tiers
              </div>
            </div>
            <div class="bt-tiers">
              <div
                v-for="tier in ['HIGH', 'MEDIUM', 'LOW']"
                :key="tier"
                class="bt-tier-row"
                v-if="currentRun.metrics.confidence_tier_metrics[tier]"
              >
                <div class="tier-label" :class="'tier-' + tier.toLowerCase()">{{ tier }}</div>
                <div class="tier-bar-wrap">
                  <div
                    class="tier-bar"
                    :class="'tier-bar-' + tier.toLowerCase()"
                    :style="{ width: ((currentRun.metrics.confidence_tier_metrics[tier].accuracy || 0) * 100) + '%' }"
                  ></div>
                </div>
                <div class="tier-val">{{ formatPct(currentRun.metrics.confidence_tier_metrics[tier].accuracy) }}</div>
                <div class="tier-n">n={{ currentRun.metrics.confidence_tier_metrics[tier].markets_tested }}</div>
              </div>
            </div>
          </div>

          <!-- Market-by-Market Results Table -->
          <div v-if="currentRun && currentRun.results && currentRun.results.length > 0" class="bt-panel">
            <div class="bt-panel-head">
              <div class="bt-panel-title">
                <span class="bt-dot"></span>
                Market Results
              </div>
              <span class="bt-results-count">{{ currentRun.results.length }} markets</span>
            </div>
            <div class="bt-table-wrap">
              <table class="bt-table">
                <thead>
                  <tr>
                    <th class="sortable" @click="sortBy('market')">
                      Market <span class="sort-arrow">{{ sortArrow('market') }}</span>
                    </th>
                    <th class="sortable" @click="sortBy('category')">
                      Category <span class="sort-arrow">{{ sortArrow('category') }}</span>
                    </th>
                    <th class="sortable" @click="sortBy('predicted')">
                      Predicted <span class="sort-arrow">{{ sortArrow('predicted') }}</span>
                    </th>
                    <th class="sortable" @click="sortBy('actual')">
                      Actual <span class="sort-arrow">{{ sortArrow('actual') }}</span>
                    </th>
                    <th class="sortable" @click="sortBy('signal')">
                      Signal <span class="sort-arrow">{{ sortArrow('signal') }}</span>
                    </th>
                    <th class="sortable" @click="sortBy('edge')">
                      Edge <span class="sort-arrow">{{ sortArrow('edge') }}</span>
                    </th>
                    <th class="sortable" @click="sortBy('correct')">
                      Correct <span class="sort-arrow">{{ sortArrow('correct') }}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, idx) in sortedResults"
                    :key="idx"
                    class="bt-table-row fade-in"
                    :style="{ animationDelay: (idx * 20) + 'ms' }"
                  >
                    <td class="col-market">{{ truncate(row.market || row.market_title || '-', 50) }}</td>
                    <td><span v-if="row.category" class="category-badge">{{ row.category }}</span><span v-else>-</span></td>
                    <td class="col-num">{{ formatPct(row.predicted) }}</td>
                    <td class="col-num">{{ formatPct(row.actual) }}</td>
                    <td>
                      <span class="signal-badge-sm" :class="signalClass(row.signal)">
                        {{ row.signal || '-' }}
                      </span>
                    </td>
                    <td class="col-num" :class="edgeClass(row.edge)">
                      {{ row.edge != null ? (row.edge >= 0 ? '+' : '') + (row.edge * 100).toFixed(1) + '%' : '-' }}
                    </td>
                    <td class="col-center">
                      <span v-if="row.correct === true" class="correct-mark">✓</span>
                      <span v-else-if="row.correct === false" class="incorrect-mark">✗</span>
                      <span v-else class="pending-mark">—</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Calibration Placeholder -->
          <div v-if="currentRun" class="bt-panel">
            <div class="bt-panel-head">
              <div class="bt-panel-title">
                <span class="bt-dot"></span>
                Calibration
              </div>
            </div>
            <div class="bt-calibration-placeholder">
              Calibration chart requires ≥20 data points
            </div>
          </div>

        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { startBacktest, getBacktestRun, listBacktests } from '../api/backtest'

// ═══════ STATE ═══════
const marketCount = ref(50)
const isRunning = ref(false)
const loadingHistory = ref(false)
const loadingRun = ref(false)
const errorMsg = ref('')
const backtestRuns = ref([])
const currentRun = ref(null)
const activeRunId = ref(null)
const sortKey = ref('')
const sortDir = ref('asc')
let pollInterval = null

// ═══════ COMPUTED ═══════
const totalMarketsTestedAll = computed(() => {
  return backtestRuns.value.reduce((sum, r) => sum + (r.metrics?.markets_tested || r.total_markets || 0), 0)
})

const roiClass = computed(() => {
  if (!currentRun.value?.metrics?.roi) return ''
  return currentRun.value.summary.roi >= 0 ? 'val-positive' : 'val-negative'
})

const sortedResults = computed(() => {
  if (!currentRun.value?.results) return []
  const arr = [...currentRun.value.results]
  if (!sortKey.value) return arr
  arr.sort((a, b) => {
    let av = a[sortKey.value]
    let bv = b[sortKey.value]
    if (sortKey.value === 'market') {
      av = (av || a.market_title || '').toLowerCase()
      bv = (bv || b.market_title || '').toLowerCase()
    }
    if (av == null) return 1
    if (bv == null) return -1
    if (av < bv) return sortDir.value === 'asc' ? -1 : 1
    if (av > bv) return sortDir.value === 'asc' ? 1 : -1
    return 0
  })
  return arr
})

// ═══════ METHODS ═══════
const formatPct = (v) => {
  if (v == null) return '-'
  return (v * 100).toFixed(1) + '%'
}
const formatNum = (v) => {
  if (v == null) return '-'
  return Number(v).toFixed(3)
}
const formatDate = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
const truncate = (s, n) => s && s.length > n ? s.substring(0, n) + '...' : s

const signalClass = (signal) => {
  if (!signal) return ''
  const s = signal.toUpperCase()
  if (s === 'BUY_YES' || s === 'BUY') return 'signal-buy-yes'
  if (s === 'BUY_NO' || s === 'SELL') return 'signal-buy-no'
  return 'signal-hold'
}

const edgeClass = (edge) => {
  if (edge == null) return ''
  return edge >= 0 ? 'val-positive' : 'val-negative'
}

const sortBy = (key) => {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

const sortArrow = (key) => {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? '↑' : '↓'
}

// ═══════ API CALLS ═══════
const runBacktest = async () => {
  if (isRunning.value) return
  isRunning.value = true
  errorMsg.value = ''
  currentRun.value = null
  try {
    const res = await startBacktest(marketCount.value)
    const resp = res.data || res
    const runId = resp.data?.run_id || resp.run_id
    activeRunId.value = runId
    currentRun.value = { id: runId, status: 'PENDING', total_markets: marketCount.value, completed_markets: 0 }
    startPolling(runId)
  } catch (e) {
    errorMsg.value = 'Failed to start backtest: ' + (e.message || '')
    isRunning.value = false
  }
}

const selectRun = async (run) => {
  activeRunId.value = run.id
  errorMsg.value = ''
  loadingRun.value = true
  try {
    const res = await getBacktestRun(run.id)
    currentRun.value = res.data || res
    if (currentRun.value.status === 'RUNNING' || currentRun.value.status === 'PENDING') {
      isRunning.value = true
      startPolling(run.id)
    }
  } catch (e) {
    errorMsg.value = 'Failed to load run: ' + (e.message || '')
  } finally {
    loadingRun.value = false
  }
}

const loadBacktests = async () => {
  loadingHistory.value = true
  try {
    const res = await listBacktests()
    backtestRuns.value = res.data || res || []
  } catch (e) {
    console.error('Failed to load backtests:', e)
  } finally {
    loadingHistory.value = false
  }
}

const startPolling = (runId) => {
  stopPolling()
  pollInterval = setInterval(async () => {
    try {
      const res = await getBacktestRun(runId)
      const data = res.data || res
      currentRun.value = data
      if (data.status === 'COMPLETED' || data.status === 'FAILED') {
        stopPolling()
        isRunning.value = false
        loadBacktests()
      }
    } catch (e) {
      console.error('Poll error:', e)
    }
  }, 5000)
}

const stopPolling = () => {
  if (pollInterval) { clearInterval(pollInterval); pollInterval = null }
}

// ═══════ LIFECYCLE ═══════
onMounted(() => { loadBacktests() })
onUnmounted(() => { stopPolling() })
</script>

<style scoped>
/* ═══════ VARIABLES ═══════ */
:root {
  --mono: 'JetBrains Mono', 'SF Mono', monospace;
  --sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  --orange: #FF4500;
  --green: #10B981;
  --red: #dc2626;
  --border: #EAEAEA;
  --bg-subtle: #FAFAFA;
  --text-primary: #000;
  --text-secondary: #666;
  --text-muted: #999;
}

/* ═══════ PAGE ═══════ */
.backtest-page {
  min-height: 100vh;
  background: #fff;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

/* ═══════ NAVBAR ═══════ */
.bt-nav {
  height: 60px;
  background: #000;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 40px;
}
.bt-nav-left { cursor: pointer; }
.bt-nav-brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.15rem;
}
.bt-nav-center {
  display: flex;
  align-items: center;
  gap: 12px;
}
.bt-nav-links {
  display: flex;
  align-items: center;
  gap: 4px;
}
.bt-nav-link {
  background: none;
  border: 1px solid rgba(255,255,255,0.15);
  color: rgba(255,255,255,0.6);
  padding: 5px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}
.bt-nav-link:hover {
  border-color: rgba(255,255,255,0.4);
  color: rgba(255,255,255,0.9);
}
.bt-nav-link.active {
  border-color: #FF4500;
  color: #FF4500;
}
.paper-badge {
  background: #FF4500;
  color: #000;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 2px 6px;
  letter-spacing: 0.1em;
  font-family: 'JetBrains Mono', monospace;
  text-transform: uppercase;
}
.bt-nav-right { display: flex; align-items: center; }
.bt-nav-back {
  background: none;
  border: 1px solid rgba(255,255,255,0.2);
  color: rgba(255,255,255,0.7);
  padding: 6px 18px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}
.bt-nav-back:hover { border-color: #FF4500; color: #FF4500; }
.back-arrow { font-size: 1rem; }

/* ═══════ HERO STRIP ═══════ */
.bt-hero {
  border-bottom: 1px solid #EAEAEA;
  background: #FAFAFA;
}
.bt-hero-inner {
  max-width: 1400px;
  margin: 0 auto;
  padding: 14px 40px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.bt-hero-left {
  display: flex;
  align-items: center;
  gap: 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  letter-spacing: 1.5px;
  color: #999;
}
.bt-hero-tag { text-transform: uppercase; }
.bt-hero-tag.accent { color: #FF4500; }
.bt-hero-sep { color: #DDD; }
.bt-hero-right { display: flex; gap: 30px; }
.bt-hero-stat { display: flex; flex-direction: column; align-items: center; }
.bt-hero-stat-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.3rem;
  font-weight: 700;
  color: #000;
}
.bt-hero-stat-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* ═══════ MAIN LAYOUT ═══════ */
.bt-main {
  max-width: 1400px;
  margin: 0 auto;
  padding: 30px 40px 60px;
}
.bt-grid {
  display: grid;
  grid-template-columns: 1fr 1.3fr;
  gap: 30px;
  align-items: start;
}

/* ═══════ PANELS ═══════ */
.bt-panel {
  border: 1px solid #EAEAEA;
  background: #fff;
  margin-bottom: 20px;
}
.bt-panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #F5F5F5;
}
.bt-panel-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.bt-dot {
  width: 8px;
  height: 8px;
  background: #FF4500;
  display: inline-block;
}
.bt-dot.error-dot { background: #dc2626; }

/* ═══════ SMALL BUTTON ═══════ */
.bt-btn-sm {
  background: none;
  border: 1px solid #E5E5E5;
  padding: 4px 14px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: #999;
  cursor: pointer;
  transition: all 0.2s;
}
.bt-btn-sm:hover { border-color: #000; color: #000; }

/* ═══════ RUN FORM ═══════ */
.bt-run-form { padding: 20px; }
.bt-form-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.bt-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  min-width: 100px;
}
.bt-input {
  flex: 1;
  border: 1px solid #EAEAEA;
  padding: 8px 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
  background: #FAFAFA;
  outline: revert;
  transition: border-color 0.2s;
}
.bt-input:focus { border-color: #999; }

/* ═══════ RUN BUTTON ═══════ */
.bt-run-btn {
  width: 100%;
  background: #000;
  color: #fff;
  border: none;
  padding: 16px 20px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 0.95rem;
  letter-spacing: 0.5px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.2s;
}
.bt-run-btn:hover:not(.disabled) { background: #FF4500; }
.bt-run-btn.disabled { background: #333; cursor: not-allowed; }
.run-btn-arrow { font-size: 1.2rem; }
.running-text { display: flex; align-items: center; gap: 10px; }
.run-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
}

/* ═══════ HISTORY ═══════ */
.bt-history {
  max-height: 350px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #DDD #F5F5F5;
}
.bt-history::-webkit-scrollbar { width: 4px; }
.bt-history::-webkit-scrollbar-track { background: #F5F5F5; }
.bt-history::-webkit-scrollbar-thumb { background: #DDD; }

.history-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid #F5F5F5;
  cursor: pointer;
  transition: background 0.15s;
  gap: 12px;
}
.history-row:hover { background: #FAFAFA; }
.history-row.active { background: #FFF8F5; }
.history-left { flex: 1; min-width: 0; }
.history-title {
  font-size: 0.85rem;
  font-weight: 500;
  line-height: 1.3;
  font-family: 'JetBrains Mono', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.history-date {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: #CCC;
  margin-top: 3px;
}
.history-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.history-status {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 8px;
  letter-spacing: 0.5px;
}
.status-COMPLETED { color: #10B981; background: #ECFDF5; }
.status-FAILED { color: #dc2626; background: #FEF2F2; }
.status-RUNNING, .status-PENDING, .status-COMPUTING_METRICS { color: #FF4500; background: #FFF5F0; }
.history-progress {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: #FF4500;
}

/* ═══════ PAPER TRADING ═══════ */
.bt-paper-status { padding: 20px; }
.paper-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.paper-dot {
  width: 8px;
  height: 8px;
  display: inline-block;
}
.paper-dot.enabled { background: #10B981; }
.paper-dot.disabled { background: #dc2626; }
.paper-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  font-weight: 600;
}
.paper-hint {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: #BBB;
  line-height: 1.5;
}

/* ═══════ ERROR PANEL ═══════ */
.panel-error { border-color: #dc2626; }
.error-msg {
  padding: 16px 20px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  color: #dc2626;
  line-height: 1.5;
}

/* ═══════ EMPTY STATE ═══════ */
.bt-empty-state {
  padding: 50px 20px;
  text-align: center;
}
.empty-icon { font-size: 2rem; margin-bottom: 12px; color: #DDD; }
.empty-text { font-weight: 500; color: #999; margin-bottom: 6px; }
.empty-hint {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #CCC;
  max-width: 300px;
  margin: 0 auto;
  line-height: 1.5;
}
.bt-empty-mini {
  padding: 20px;
  text-align: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #CCC;
}

/* ═══════ SKELETON LOADING ═══════ */
.bt-skeleton {
  padding: 14px 20px;
  border-bottom: 1px solid #F5F5F5;
}
.skel-line {
  height: 12px;
  background: linear-gradient(90deg, #F0F0F0 25%, #E5E5E5 50%, #F0F0F0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.skel-title { width: 80%; margin-bottom: 10px; }
.skel-meta { width: 50%; height: 10px; }
.bt-skeleton-results {
  display: flex;
  gap: 1px;
  background: #F0F0F0;
  padding: 0;
}
.skel-metric-card {
  flex: 1;
  background: #fff;
  padding: 20px;
  text-align: center;
}
.skel-val { width: 60%; height: 20px; margin: 0 auto 8px; }
.skel-label { width: 80%; height: 10px; margin: 0 auto; }

/* ═══════ PROGRESS BADGE ═══════ */
.bt-progress-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 600;
  color: #FF4500;
  padding: 10px 20px;
  border: 1px solid #FF4500;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.progress-pulse {
  width: 8px;
  height: 8px;
  background: #FF4500;
  display: inline-block;
  animation: pulse-dot 1.5s infinite;
}

/* ═══════ STATUS BADGES ═══════ */
.status-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 4px 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.status-badge.completed { background: #ECFDF5; color: #10B981; }
.status-badge.failed { background: #FEF2F2; color: #dc2626; }

/* ═══════ HERO METRICS ═══════ */
.bt-metrics-grid {
  display: flex;
  gap: 1px;
  background: #F0F0F0;
}
.bt-metric-card {
  flex: 1;
  background: #fff;
  padding: 20px;
  text-align: center;
}
.bt-metric-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.3rem;
  font-weight: 700;
  margin-bottom: 4px;
}
.bt-metric-val.val-positive { color: #10B981; }
.bt-metric-val.val-negative { color: #dc2626; }
.bt-metric-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: #BBB;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* ═══════ RESULTS TABLE ═══════ */
.bt-results-count {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: #BBB;
}
.bt-table-wrap {
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: #DDD #F5F5F5;
}
.bt-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}
.bt-table thead {
  border-bottom: 1px solid #EAEAEA;
}
.bt-table th {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 10px 14px;
  text-align: left;
  white-space: nowrap;
}
.bt-table th.sortable {
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}
.bt-table th.sortable:hover { color: #000; }
.sort-arrow {
  font-size: 0.7rem;
  color: #FF4500;
}
.bt-table td {
  padding: 10px 14px;
  border-bottom: 1px solid #F5F5F5;
  color: #333;
}
.bt-table-row { transition: background 0.15s; }
.bt-table-row:hover { background: #FAFAFA; }
.col-market {
  max-width: 250px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.col-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  font-weight: 500;
}
.col-center { text-align: center; }
.col-num.val-positive { color: #10B981; }
.col-num.val-negative { color: #dc2626; }

/* Signal badges in table */
.signal-badge-sm {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 2px 8px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.signal-badge-sm.signal-buy-yes { background: #ECFDF5; color: #10B981; }
.signal-badge-sm.signal-buy-no { background: #FEF2F2; color: #dc2626; }
.signal-badge-sm.signal-hold { background: #F5F5F5; color: #999; }

/* Correct/incorrect marks */
.correct-mark {
  font-family: 'JetBrains Mono', monospace;
  color: #10B981;
  font-weight: 700;
  font-size: 1rem;
}
.incorrect-mark {
  font-family: 'JetBrains Mono', monospace;
  color: #dc2626;
  font-weight: 700;
  font-size: 1rem;
}
.pending-mark {
  color: #CCC;
}

/* ═══════ CATEGORY BADGE ═══════ */
.category-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  font-weight: 600;
  padding: 2px 8px;
  background: #F5F5F5;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

/* ═══════ CONFIDENCE TIERS ═══════ */
.bt-tiers { padding: 16px 20px; }
.bt-tier-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.tier-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 700;
  width: 60px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.tier-label.tier-high { color: #10B981; }
.tier-label.tier-medium { color: #F59E0B; }
.tier-label.tier-low { color: #999; }
.tier-bar-wrap {
  flex: 1;
  height: 16px;
  background: #F5F5F5;
  overflow: hidden;
}
.tier-bar {
  height: 100%;
  transition: width 0.5s ease;
}
.tier-bar-high { background: #10B981; }
.tier-bar-medium { background: #F59E0B; }
.tier-bar-low { background: #DDD; }
.tier-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  font-weight: 600;
  width: 50px;
  text-align: right;
}
.tier-n {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: #BBB;
  width: 40px;
}

/* ═══════ CALIBRATION PLACEHOLDER ═══════ */
.bt-calibration-placeholder {
  padding: 40px 20px;
  text-align: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #CCC;
}

/* ═══════ ANIMATIONS ═══════ */
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.fade-in {
  animation: fadeInUp 0.3s ease both;
}

/* ═══════ RESPONSIVE ═══════ */
@media (max-width: 1024px) {
  .bt-grid { grid-template-columns: 1fr; }
  .bt-col-left { order: 1; }
  .bt-col-right { order: 2; }
  .bt-main { padding: 20px; }
  .bt-nav { padding: 0 20px; }
  .bt-hero-inner { padding: 12px 20px; }
  .bt-hero-left { display: none; }
}
@media (max-width: 768px) {
  .bt-nav-center { display: none; }
  .bt-hero-right { gap: 16px; }
  .bt-metrics-grid { flex-direction: column; gap: 0; }
  .bt-calibration-placeholder { display: none; }
}
</style>
