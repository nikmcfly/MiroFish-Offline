<template>
  <div class="prediction-page">
    <!-- ═══════ NAVBAR ═══════ -->
    <nav class="pred-nav">
      <div class="pred-nav-left" @click="$router.push('/')">
        <span class="pred-nav-brand">MIROFISH OFFLINE</span>
      </div>
      <div class="pred-nav-center">
        <div class="pred-nav-indicator">
          <span class="pred-nav-dot"></span>
          Prediction Market Engine
        </div>
      </div>
      <div class="pred-nav-right">
        <button class="pred-nav-back" @click="$router.push('/')">
          <span class="back-arrow">←</span> Home
        </button>
      </div>
    </nav>

    <!-- ═══════ HERO STRIP ═══════ -->
    <div class="pred-hero">
      <div class="pred-hero-inner">
        <div class="pred-hero-left">
          <span class="pred-hero-tag">POLYMARKET</span>
          <span class="pred-hero-sep">/</span>
          <span class="pred-hero-tag accent">MULTI-AGENT SIMULATION</span>
          <span class="pred-hero-sep">/</span>
          <span class="pred-hero-tag">SIGNAL GENERATION</span>
        </div>
        <div class="pred-hero-right">
          <div class="pred-hero-stat">
            <span class="pred-hero-stat-val">{{ markets.length }}</span>
            <span class="pred-hero-stat-label">Markets</span>
          </div>
          <div class="pred-hero-stat">
            <span class="pred-hero-stat-val">{{ history.length }}</span>
            <span class="pred-hero-stat-label">Runs</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════ MAIN CONTENT ═══════ -->
    <div class="pred-main">
      <div class="pred-grid">

        <!-- ══════════════ LEFT PANEL: MARKET BROWSER ══════════════ -->
        <div class="pred-col pred-col-left">
          <div class="pred-panel">
            <!-- Panel Header -->
            <div class="pred-panel-head">
              <div class="pred-panel-title">
                <span class="pred-dot"></span>
                Active Markets
              </div>
              <button
                class="pred-btn-sm"
                :class="{ loading: loadingMarkets }"
                @click="loadMarkets"
                :disabled="loadingMarkets"
              >
                <span class="btn-spinner" v-if="loadingMarkets"></span>
                {{ loadingMarkets ? '' : 'Refresh' }}
              </button>
            </div>

            <!-- Filters -->
            <div class="pred-filters">
              <div class="pred-search-wrap">
                <span class="search-icon">⌕</span>
                <input
                  v-model="searchQuery"
                  class="pred-search"
                  placeholder="Search markets..."
                  @keyup.enter="loadMarkets"
                />
              </div>
              <select v-model="minVolume" class="pred-select" @change="loadMarkets">
                <option :value="1000">$1K+</option>
                <option :value="10000">$10K+</option>
                <option :value="100000">$100K+</option>
                <option :value="1000000">$1M+</option>
              </select>
            </div>

            <!-- Error -->
            <div v-if="marketsError" class="pred-error">
              <span class="error-icon">!</span>
              {{ marketsError }}
            </div>

            <!-- Market List -->
            <div class="pred-market-list" ref="marketListRef">
              <!-- Loading skeleton -->
              <template v-if="loadingMarkets && markets.length === 0">
                <div v-for="i in 6" :key="'skel-'+i" class="pred-market-skeleton">
                  <div class="skel-line skel-title"></div>
                  <div class="skel-line skel-meta"></div>
                </div>
              </template>

              <!-- Empty state -->
              <div v-if="!loadingMarkets && markets.length === 0 && !marketsError" class="pred-empty">
                <div class="empty-icon">◇</div>
                <div>No markets found</div>
                <div class="empty-hint">Adjust filters or click Refresh</div>
              </div>

              <!-- Market cards -->
              <div
                v-for="(market, idx) in markets"
                :key="market.condition_id"
                class="pred-market-card"
                :class="{
                  selected: selectedMarket?.condition_id === market.condition_id,
                  'fade-in': true
                }"
                :style="{ animationDelay: (idx * 30) + 'ms' }"
                @click="selectMarket(market)"
              >
                <div class="market-card-top">
                  <div class="market-card-title">{{ market.title }}</div>
                </div>
                <div class="market-card-bottom">
                  <div class="market-prices">
                    <span class="price-badge yes">
                      YES {{ formatPercent(market.prices[0]) }}
                    </span>
                    <span class="price-badge no">
                      NO {{ formatPercent(market.prices[1]) }}
                    </span>
                  </div>
                  <div class="market-vol">${{ formatNumber(market.volume) }}</div>
                </div>
                <!-- Probability bar -->
                <div class="market-prob-bar">
                  <div
                    class="market-prob-fill"
                    :style="{ width: (market.prices[0] * 100) + '%' }"
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ══════════════ RIGHT PANEL: RUN + RESULTS ══════════════ -->
        <div class="pred-col pred-col-right">

          <!-- ─── SELECTED MARKET + RUN TRIGGER ─── -->
          <div class="pred-panel" :class="{ 'panel-active': selectedMarket }">
            <div class="pred-panel-head">
              <div class="pred-panel-title">
                <span class="pred-dot"></span>
                Prediction Run
              </div>
              <div v-if="selectedMarket" class="panel-market-prices">
                <span class="panel-price yes">{{ formatPercent(selectedMarket.prices[0]) }}</span>
                <span class="panel-price-sep">/</span>
                <span class="panel-price no">{{ formatPercent(selectedMarket.prices[1]) }}</span>
              </div>
            </div>

            <!-- Empty: no market selected -->
            <div v-if="!selectedMarket" class="pred-empty-run">
              <div class="empty-run-icon">
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                  <rect x="4" y="4" width="40" height="40" stroke="#E5E5E5" stroke-width="1.5" fill="none"/>
                  <path d="M16 24h16M24 16v16" stroke="#DDD" stroke-width="1.5"/>
                </svg>
              </div>
              <div class="empty-run-text">Select a market to begin</div>
              <div class="empty-run-hint">The pipeline will simulate agent discourse and generate a trading signal</div>
            </div>

            <!-- Market selected -->
            <div v-else class="pred-selected">
              <div class="selected-title">{{ selectedMarket.title }}</div>
              <div v-if="selectedMarket.description" class="selected-desc">
                {{ truncate(selectedMarket.description, 250) }}
              </div>

              <!-- Market quick stats -->
              <div class="selected-stats">
                <div class="selected-stat">
                  <span class="stat-label">Volume</span>
                  <span class="stat-value">${{ formatNumber(selectedMarket.volume) }}</span>
                </div>
                <div class="selected-stat">
                  <span class="stat-label">Liquidity</span>
                  <span class="stat-value">${{ formatNumber(selectedMarket.liquidity) }}</span>
                </div>
                <div class="selected-stat">
                  <span class="stat-label">Ends</span>
                  <span class="stat-value">{{ formatDateShort(selectedMarket.end_date) }}</span>
                </div>
              </div>

              <!-- Run button -->
              <button
                class="pred-run-btn"
                :class="{ disabled: !!activeRun, running: !!activeRun }"
                @click="startRun"
                :disabled="!!activeRun"
              >
                <span class="run-btn-label">
                  <span v-if="!activeRun">Run Prediction</span>
                  <span v-else class="running-text">
                    <span class="run-spinner"></span>
                    Pipeline Running...
                  </span>
                </span>
                <span class="run-btn-arrow" v-if="!activeRun">→</span>
              </button>
            </div>
          </div>

          <!-- ─── PIPELINE PROGRESS ─── -->
          <transition name="panel-slide">
            <div v-if="activeRun" class="pred-panel panel-progress">
              <div class="pred-panel-head">
                <div class="pred-panel-title">
                  <span class="pred-dot pulse"></span>
                  Pipeline
                </div>
                <div class="progress-pct">{{ progressPercent }}%</div>
              </div>

              <!-- Pipeline stages -->
              <div class="pipeline-stages">
                <div
                  v-for="(stage, idx) in pipelineStages"
                  :key="stage.key"
                  class="pipeline-stage"
                  :class="{
                    done: stageIndex(activeRun.status) > idx,
                    active: stageIndex(activeRun.status) === idx,
                    pending: stageIndex(activeRun.status) < idx
                  }"
                >
                  <div class="stage-indicator">
                    <div class="stage-dot">
                      <span v-if="stageIndex(activeRun.status) > idx" class="stage-check">✓</span>
                      <span v-else-if="stageIndex(activeRun.status) === idx" class="stage-pulse"></span>
                    </div>
                    <div v-if="idx < pipelineStages.length - 1" class="stage-line"
                      :class="{ filled: stageIndex(activeRun.status) > idx }"
                    ></div>
                  </div>
                  <div class="stage-info">
                    <div class="stage-name">{{ stage.label }}</div>
                    <div class="stage-desc">{{ stage.desc }}</div>
                  </div>
                </div>
              </div>

              <!-- Progress bar -->
              <div class="pipeline-bar">
                <div class="pipeline-bar-fill" :style="{ width: progressPercent + '%' }"></div>
              </div>
              <div class="pipeline-msg">{{ activeRun.progress_message }}</div>
            </div>
          </transition>

          <!-- ─── SIGNAL RESULT ─── -->
          <transition name="panel-slide">
            <div v-if="completedRun && completedRun.signal" class="pred-panel panel-signal">
              <div class="pred-panel-head">
                <div class="pred-panel-title">
                  <span class="pred-dot"></span>
                  Trading Signal
                </div>
                <span class="signal-badge" :class="signalClass">
                  {{ completedRun.signal.direction.replace('_', ' ') }}
                </span>
              </div>

              <!-- Probability comparison gauge -->
              <div class="signal-gauge">
                <div class="gauge-row">
                  <div class="gauge-label">Market</div>
                  <div class="gauge-bar-wrap">
                    <div class="gauge-bar market-bar" :style="{ width: (completedRun.signal.market_probability * 100) + '%' }"></div>
                  </div>
                  <div class="gauge-val">{{ formatPercent(completedRun.signal.market_probability) }}</div>
                </div>
                <div class="gauge-row">
                  <div class="gauge-label">Simulated</div>
                  <div class="gauge-bar-wrap">
                    <div class="gauge-bar sim-bar" :class="signalClass" :style="{ width: (completedRun.signal.simulated_probability * 100) + '%' }"></div>
                  </div>
                  <div class="gauge-val">{{ formatPercent(completedRun.signal.simulated_probability) }}</div>
                </div>
              </div>

              <!-- Signal metrics -->
              <div class="signal-metrics">
                <div class="signal-metric">
                  <div class="metric-val" :class="signalClass">
                    {{ completedRun.signal.edge >= 0 ? '+' : '' }}{{ (completedRun.signal.edge * 100).toFixed(1) }}%
                  </div>
                  <div class="metric-label">Edge</div>
                </div>
                <div class="signal-metric">
                  <div class="metric-val">{{ (completedRun.signal.confidence * 100).toFixed(0) }}%</div>
                  <div class="metric-label">Confidence</div>
                </div>
                <div class="signal-metric" v-if="completedRun.sentiment">
                  <div class="metric-val">{{ completedRun.sentiment.total_posts_analyzed }}</div>
                  <div class="metric-label">Posts Analyzed</div>
                </div>
              </div>

              <!-- Reasoning -->
              <div class="signal-reasoning">
                {{ completedRun.signal.reasoning }}
              </div>

              <!-- ─── SENTIMENT BREAKDOWN ─── -->
              <div v-if="completedRun.sentiment" class="sentiment-section">
                <div class="sentiment-head">Stance Distribution</div>

                <!-- Stance bar -->
                <div class="stance-bar-wrap">
                  <div class="stance-bar for-bar" :style="{ width: stancePercent('for') + '%' }"></div>
                  <div class="stance-bar neutral-bar" :style="{ width: stancePercent('neutral') + '%' }"></div>
                  <div class="stance-bar against-bar" :style="{ width: stancePercent('against') + '%' }"></div>
                </div>
                <div class="stance-legend">
                  <span class="stance-item for">
                    <span class="stance-dot for-dot"></span>
                    For {{ completedRun.sentiment.stance_counts.for }}
                  </span>
                  <span class="stance-item neutral">
                    <span class="stance-dot neutral-dot"></span>
                    Neutral {{ completedRun.sentiment.stance_counts.neutral }}
                  </span>
                  <span class="stance-item against">
                    <span class="stance-dot against-dot"></span>
                    Against {{ completedRun.sentiment.stance_counts.against }}
                  </span>
                </div>

                <!-- Key arguments -->
                <div v-if="completedRun.sentiment.key_arguments_for.length" class="args-block">
                  <div class="args-title for-title">Key Arguments For</div>
                  <div v-for="(arg, i) in completedRun.sentiment.key_arguments_for" :key="'f-'+i" class="arg-item">
                    <span class="arg-bullet for-bullet"></span>
                    {{ arg }}
                  </div>
                </div>
                <div v-if="completedRun.sentiment.key_arguments_against.length" class="args-block">
                  <div class="args-title against-title">Key Arguments Against</div>
                  <div v-for="(arg, i) in completedRun.sentiment.key_arguments_against" :key="'a-'+i" class="arg-item">
                    <span class="arg-bullet against-bullet"></span>
                    {{ arg }}
                  </div>
                </div>
              </div>
            </div>
          </transition>

          <!-- ─── FAILED STATE ─── -->
          <div v-if="completedRun && completedRun.status === 'failed'" class="pred-panel panel-failed">
            <div class="pred-panel-head">
              <div class="pred-panel-title">
                <span class="pred-dot failed-dot"></span>
                Run Failed
              </div>
            </div>
            <div class="failed-msg">{{ completedRun.error || 'An unknown error occurred' }}</div>
          </div>

          <!-- ─── HISTORY ─── -->
          <div class="pred-panel">
            <div class="pred-panel-head">
              <div class="pred-panel-title">
                <span class="pred-dot"></span>
                Run History
              </div>
              <button class="pred-btn-sm" @click="loadHistory">Refresh</button>
            </div>
            <div class="pred-history">
              <div v-if="history.length === 0" class="pred-empty-mini">No prediction runs yet</div>
              <div
                v-for="run in history"
                :key="run.run_id"
                class="history-row"
                :class="{ active: completedRun?.run_id === run.run_id }"
                @click="viewRun(run)"
              >
                <div class="history-left">
                  <div class="history-title">{{ run.market?.title || run.run_id }}</div>
                  <div class="history-date">{{ formatDate(run.created_at) }}</div>
                </div>
                <div class="history-right">
                  <span class="history-status" :class="'status-' + run.status">
                    {{ run.status }}
                  </span>
                  <span v-if="run.signal" class="history-signal" :class="signalClassFor(run.signal.direction)">
                    {{ run.signal.direction.replace('_', ' ') }}
                    <span class="history-edge">{{ run.signal.edge >= 0 ? '+' : '' }}{{ (run.signal.edge * 100).toFixed(1) }}%</span>
                  </span>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fetchMarkets, startPredictionRun, getRunStatus, getRun, listRuns } from '../api/prediction'

// ═══════ PIPELINE STAGE DEFINITIONS ═══════
const pipelineStages = [
  { key: 'fetching_market', label: 'Fetch Market', desc: 'Loading market data' },
  { key: 'generating_scenario', label: 'Generate Scenario', desc: 'LLM creates balanced context' },
  { key: 'running_simulation', label: 'Simulate Debate', desc: 'Multi-perspective discourse via LLM' },
  { key: 'analyzing', label: 'Compute Signal', desc: 'Probability estimation from stances' },
]

// ═══════ STATE ═══════
const markets = ref([])
const loadingMarkets = ref(false)
const marketsError = ref('')
const searchQuery = ref('')
const minVolume = ref(10000)
const selectedMarket = ref(null)
const activeRun = ref(null)
const completedRun = ref(null)
const history = ref([])
const marketListRef = ref(null)
let pollInterval = null

// ═══════ COMPUTED ═══════
const progressPercent = computed(() => {
  if (!activeRun.value) return 0
  const map = {
    fetching_market: 5, generating_scenario: 25,
    running_simulation: 60, analyzing: 90, completed: 100,
  }
  return map[activeRun.value.status] || 0
})

const signalClass = computed(() => {
  if (!completedRun.value?.signal) return ''
  const d = completedRun.value.signal.direction
  if (d === 'BUY_YES') return 'signal-buy-yes'
  if (d === 'BUY_NO') return 'signal-buy-no'
  return 'signal-hold'
})

// ═══════ METHODS ═══════
const stageIndex = (status) => {
  const idx = pipelineStages.findIndex(s => s.key === status)
  return idx >= 0 ? idx : (status === 'completed' ? pipelineStages.length : -1)
}

const formatPercent = (v) => ((v || 0) * 100).toFixed(0) + '%'
const formatNumber = (n) => {
  if (!n) return '0'
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (n >= 1e3) return (n / 1e3).toFixed(0) + 'K'
  return n.toFixed(0)
}
const formatDate = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
const formatDateShort = (iso) => {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
const truncate = (s, n) => s && s.length > n ? s.substring(0, n) + '...' : s

const signalClassFor = (dir) => {
  if (dir === 'BUY_YES') return 'signal-buy-yes'
  if (dir === 'BUY_NO') return 'signal-buy-no'
  return 'signal-hold'
}

const stancePercent = (type) => {
  if (!completedRun.value?.sentiment) return 0
  const counts = completedRun.value.sentiment.stance_counts
  const total = (counts.for || 0) + (counts.against || 0) + (counts.neutral || 0)
  if (total === 0) return 0
  return ((counts[type] || 0) / total * 100).toFixed(1)
}

const statusStyle = (status) => {
  const colors = { completed: '#10B981', failed: '#dc2626' }
  return colors[status] || '#FF4500'
}

// ═══════ API CALLS ═══════
const loadMarkets = async () => {
  loadingMarkets.value = true
  marketsError.value = ''
  try {
    const res = await fetchMarkets({
      min_volume: minVolume.value,
      limit: 50,
      search: searchQuery.value || undefined,
    })
    markets.value = res.data || []
  } catch (e) {
    marketsError.value = e.message || 'Failed to load markets'
    markets.value = []
  } finally {
    loadingMarkets.value = false
  }
}

const selectMarket = (market) => { selectedMarket.value = market }

const startRun = async () => {
  if (!selectedMarket.value || activeRun.value) return
  marketsError.value = ''
  try {
    const res = await startPredictionRun(selectedMarket.value)
    const { run_id } = res.data
    activeRun.value = { run_id, status: 'fetching_market', progress_message: 'Starting pipeline...' }
    completedRun.value = null
    startPolling(run_id)
  } catch (e) {
    marketsError.value = 'Failed to start: ' + (e.message || '')
  }
}

const startPolling = (runId) => {
  stopPolling()
  pollInterval = setInterval(async () => {
    try {
      const res = await getRunStatus(runId)
      const data = res.data
      activeRun.value = data
      if (data.status === 'completed' || data.status === 'failed') {
        stopPolling()
        activeRun.value = null
        const fullRes = await getRun(runId)
        completedRun.value = fullRes.data
        loadHistory()
      }
    } catch (e) { console.error('Poll error:', e) }
  }, 3000)
}

const stopPolling = () => {
  if (pollInterval) { clearInterval(pollInterval); pollInterval = null }
}

const viewRun = async (run) => {
  try {
    const res = await getRun(run.run_id)
    completedRun.value = res.data
  } catch (e) { console.error('Failed to load run:', e) }
}

const loadHistory = async () => {
  try {
    const res = await listRuns(20)
    history.value = res.data || []
  } catch (e) { console.error('Failed to load history:', e) }
}

// ═══════ LIFECYCLE ═══════
onMounted(() => { loadMarkets(); loadHistory() })
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
.prediction-page {
  min-height: 100vh;
  background: #fff;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

/* ═══════ NAVBAR ═══════ */
.pred-nav {
  height: 60px;
  background: #000;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 40px;
}
.pred-nav-left { cursor: pointer; }
.pred-nav-brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.15rem;
}
.pred-nav-center { display: flex; align-items: center; }
.pred-nav-indicator {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: rgba(255,255,255,0.6);
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(255,255,255,0.15);
  padding: 5px 16px;
}
.pred-nav-dot {
  width: 6px; height: 6px;
  background: #FF4500;
  border-radius: 50%;
  display: inline-block;
  animation: pulse-dot 2s infinite;
}
.pred-nav-right { display: flex; align-items: center; }
.pred-nav-back {
  background: none; border: 1px solid rgba(255,255,255,0.2);
  color: rgba(255,255,255,0.7); padding: 6px 18px;
  font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;
  cursor: pointer; transition: all 0.2s;
  display: flex; align-items: center; gap: 6px;
}
.pred-nav-back:hover { border-color: #FF4500; color: #FF4500; }
.back-arrow { font-size: 1rem; }

/* ═══════ HERO STRIP ═══════ */
.pred-hero {
  border-bottom: 1px solid #EAEAEA;
  background: #FAFAFA;
}
.pred-hero-inner {
  max-width: 1400px; margin: 0 auto;
  padding: 14px 40px;
  display: flex; justify-content: space-between; align-items: center;
}
.pred-hero-left {
  display: flex; align-items: center; gap: 12px;
  font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
  letter-spacing: 1.5px; color: #999;
}
.pred-hero-tag { text-transform: uppercase; }
.pred-hero-tag.accent { color: #FF4500; }
.pred-hero-sep { color: #DDD; }
.pred-hero-right { display: flex; gap: 30px; }
.pred-hero-stat { display: flex; flex-direction: column; align-items: center; }
.pred-hero-stat-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.3rem; font-weight: 700; color: #000;
}
.pred-hero-stat-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem; color: #999; text-transform: uppercase; letter-spacing: 1px;
}

/* ═══════ MAIN LAYOUT ═══════ */
.pred-main {
  max-width: 1400px; margin: 0 auto;
  padding: 30px 40px 60px;
}
.pred-grid {
  display: grid;
  grid-template-columns: 1fr 1.3fr;
  gap: 30px;
  align-items: start;
}

/* ═══════ PANELS ═══════ */
.pred-panel {
  border: 1px solid #EAEAEA;
  background: #fff;
  margin-bottom: 20px;
  transition: border-color 0.3s, box-shadow 0.3s;
}
.pred-panel.panel-active { border-color: #DDD; }
.pred-panel-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #F5F5F5;
}
.pred-panel-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem; color: #999;
  display: flex; align-items: center; gap: 8px;
  text-transform: uppercase; letter-spacing: 0.5px;
}
.pred-dot {
  width: 8px; height: 8px; background: #FF4500;
  display: inline-block;
}
.pred-dot.pulse { animation: pulse-dot 1.5s infinite; }
.pred-dot.failed-dot { background: #dc2626; }

/* ═══════ SMALL BUTTON ═══════ */
.pred-btn-sm {
  background: none; border: 1px solid #E5E5E5;
  padding: 4px 14px; font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; color: #999; cursor: pointer;
  transition: all 0.2s; display: flex; align-items: center; gap: 6px;
}
.pred-btn-sm:hover { border-color: #000; color: #000; }
.pred-btn-sm.loading { color: #FF4500; border-color: #FF4500; }
.btn-spinner {
  width: 12px; height: 12px; border: 1.5px solid #FF4500;
  border-top-color: transparent; border-radius: 50%;
  animation: spin 0.8s linear infinite; display: inline-block;
}

/* ═══════ FILTERS ═══════ */
.pred-filters {
  display: flex; gap: 8px; padding: 12px 20px;
  border-bottom: 1px solid #F5F5F5;
}
.pred-search-wrap {
  flex: 1; position: relative; display: flex; align-items: center;
}
.search-icon {
  position: absolute; left: 10px;
  font-size: 0.9rem; color: #CCC;
}
.pred-search {
  width: 100%; border: 1px solid #EAEAEA; padding: 7px 10px 7px 30px;
  font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;
  outline: none; background: #FAFAFA; transition: border-color 0.2s;
}
.pred-search:focus { border-color: #999; }
.pred-select {
  border: 1px solid #EAEAEA; padding: 7px 10px;
  font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;
  background: #FAFAFA; cursor: pointer; min-width: 80px;
}

/* ═══════ ERROR ═══════ */
.pred-error {
  margin: 12px 20px; padding: 10px 14px;
  background: #FEF2F2; border: 1px solid #FEE2E2;
  font-size: 0.8rem; color: #dc2626;
  font-family: 'JetBrains Mono', monospace;
  display: flex; align-items: center; gap: 8px;
}
.error-icon {
  width: 18px; height: 18px; border-radius: 50%; background: #dc2626;
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 0.65rem; font-weight: 700; flex-shrink: 0;
}

/* ═══════ MARKET LIST ═══════ */
.pred-market-list {
  max-height: 620px; overflow-y: auto;
  scrollbar-width: thin; scrollbar-color: #DDD #F5F5F5;
}
.pred-market-list::-webkit-scrollbar { width: 4px; }
.pred-market-list::-webkit-scrollbar-track { background: #F5F5F5; }
.pred-market-list::-webkit-scrollbar-thumb { background: #DDD; }

/* ═══════ MARKET CARD ═══════ */
.pred-market-card {
  padding: 14px 20px; cursor: pointer;
  border-bottom: 1px solid #F5F5F5;
  transition: all 0.15s ease;
  position: relative;
}
.pred-market-card:hover { background: #FAFAFA; }
.pred-market-card.selected {
  background: #FFF8F5;
  border-left: 3px solid #FF4500;
  padding-left: 17px;
}
.pred-market-card.fade-in {
  animation: fadeInUp 0.3s ease both;
}
.market-card-top { margin-bottom: 8px; }
.market-card-title {
  font-size: 0.9rem; font-weight: 500; line-height: 1.4; color: #000;
}
.market-card-bottom {
  display: flex; justify-content: space-between; align-items: center;
}
.market-prices { display: flex; gap: 6px; }
.price-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; font-weight: 600; padding: 2px 8px;
}
.price-badge.yes { color: #10B981; background: #ECFDF5; }
.price-badge.no { color: #dc2626; background: #FEF2F2; }
.market-vol {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; color: #BBB;
}
.market-prob-bar {
  height: 2px; background: #F0F0F0; margin-top: 10px;
  overflow: hidden;
}
.market-prob-fill {
  height: 100%; background: linear-gradient(90deg, #10B981, #10B981);
  transition: width 0.3s ease;
}

/* ═══════ SKELETON LOADING ═══════ */
.pred-market-skeleton {
  padding: 14px 20px; border-bottom: 1px solid #F5F5F5;
}
.skel-line {
  height: 12px; background: linear-gradient(90deg, #F0F0F0 25%, #E5E5E5 50%, #F0F0F0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 2px;
}
.skel-title { width: 80%; margin-bottom: 10px; }
.skel-meta { width: 50%; height: 10px; }

/* ═══════ EMPTY STATES ═══════ */
.pred-empty {
  padding: 50px 20px; text-align: center; color: #BBB;
}
.empty-icon { font-size: 2rem; margin-bottom: 12px; color: #DDD; }
.empty-hint {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem; margin-top: 6px; color: #CCC;
}
.pred-empty-run {
  padding: 40px 20px; text-align: center;
}
.empty-run-icon { margin-bottom: 16px; }
.empty-run-text { font-weight: 500; color: #999; margin-bottom: 6px; }
.empty-run-hint {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem; color: #CCC; max-width: 300px; margin: 0 auto; line-height: 1.5;
}
.pred-empty-mini {
  padding: 20px; text-align: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem; color: #CCC;
}

/* ═══════ SELECTED MARKET ═══════ */
.pred-selected { padding: 0 20px 20px; }
.selected-title {
  font-size: 1.05rem; font-weight: 520; line-height: 1.4;
  margin-bottom: 10px;
}
.selected-desc {
  font-size: 0.85rem; color: #888; line-height: 1.6; margin-bottom: 16px;
}
.selected-stats {
  display: flex; gap: 12px; margin-bottom: 16px;
}
.selected-stat {
  flex: 1; background: #FAFAFA; padding: 12px; text-align: center;
}
.stat-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem; color: #BBB; text-transform: uppercase;
  letter-spacing: 0.5px; display: block; margin-bottom: 4px;
}
.stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem; font-weight: 600; color: #333;
}
.panel-market-prices {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem; display: flex; align-items: center; gap: 4px;
}
.panel-price.yes { color: #10B981; font-weight: 600; }
.panel-price.no { color: #dc2626; font-weight: 600; }
.panel-price-sep { color: #DDD; }

/* ═══════ RUN BUTTON ═══════ */
.pred-run-btn {
  width: 100%; background: #000; color: #fff; border: none;
  padding: 16px 20px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700; font-size: 0.95rem; letter-spacing: 0.5px;
  cursor: pointer;
  display: flex; justify-content: space-between; align-items: center;
  transition: all 0.2s;
}
.pred-run-btn:hover:not(.disabled) {
  background: #FF4500;
  box-shadow: 0 4px 12px rgba(255,69,0,0.2);
  transform: translateY(-1px);
}
.pred-run-btn:active:not(.disabled) { transform: translateY(0); }
.pred-run-btn.disabled {
  background: #333; cursor: not-allowed;
}
.run-btn-arrow { font-size: 1.2rem; }
.running-text { display: flex; align-items: center; gap: 10px; }
.run-spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff; border-radius: 50%;
  animation: spin 0.8s linear infinite; display: inline-block;
}

/* ═══════ PIPELINE PROGRESS ═══════ */
.panel-progress { border-color: #FF4500; }
.progress-pct {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem; font-weight: 700; color: #FF4500;
}
.pipeline-stages { padding: 16px 20px 8px; }
.pipeline-stage {
  display: flex; gap: 14px; min-height: 44px;
}
.stage-indicator {
  display: flex; flex-direction: column; align-items: center;
  width: 20px; flex-shrink: 0;
}
.stage-dot {
  width: 16px; height: 16px; border-radius: 50%;
  border: 1.5px solid #E5E5E5; background: #fff;
  display: flex; align-items: center; justify-content: center;
  position: relative; z-index: 1;
  transition: all 0.3s;
}
.pipeline-stage.done .stage-dot {
  background: #000; border-color: #000;
}
.pipeline-stage.active .stage-dot {
  border-color: #FF4500; background: #fff;
}
.stage-check { color: #fff; font-size: 0.6rem; }
.stage-pulse {
  width: 6px; height: 6px; background: #FF4500; border-radius: 50%;
  animation: pulse-dot 1s infinite;
}
.stage-line {
  width: 1.5px; flex: 1; background: #E5E5E5;
  margin: 2px 0; transition: background 0.3s;
}
.stage-line.filled { background: #000; }
.stage-info { padding-bottom: 12px; }
.stage-name {
  font-size: 0.85rem; font-weight: 500; color: #333;
  margin-bottom: 2px;
}
.pipeline-stage.pending .stage-name { color: #CCC; }
.pipeline-stage.active .stage-name { color: #FF4500; font-weight: 600; }
.stage-desc {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; color: #BBB;
}
.pipeline-stage.active .stage-desc { color: #999; }
.pipeline-bar {
  height: 3px; background: #F0F0F0; margin: 0 20px;
  overflow: hidden;
}
.pipeline-bar-fill {
  height: 100%; background: #FF4500;
  transition: width 0.8s cubic-bezier(0.25, 0.8, 0.25, 1);
}
.pipeline-msg {
  padding: 10px 20px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem; color: #999;
}

/* ═══════ SIGNAL RESULT ═══════ */
.panel-signal { border-color: #EAEAEA; }
.signal-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; font-weight: 700;
  padding: 4px 12px; text-transform: uppercase; letter-spacing: 0.5px;
}
.signal-badge.signal-buy-yes { background: #ECFDF5; color: #10B981; }
.signal-badge.signal-buy-no { background: #FEF2F2; color: #dc2626; }
.signal-badge.signal-hold { background: #F5F5F5; color: #999; }

/* Gauge */
.signal-gauge { padding: 16px 20px; }
.gauge-row {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 10px;
}
.gauge-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; color: #999; width: 70px; text-align: right;
}
.gauge-bar-wrap {
  flex: 1; height: 8px; background: #F0F0F0; overflow: hidden;
}
.gauge-bar {
  height: 100%; transition: width 0.8s cubic-bezier(0.25, 0.8, 0.25, 1);
}
.gauge-bar.market-bar { background: #DDD; }
.gauge-bar.sim-bar.signal-buy-yes { background: #10B981; }
.gauge-bar.sim-bar.signal-buy-no { background: #dc2626; }
.gauge-bar.sim-bar.signal-hold { background: #999; }
.gauge-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem; font-weight: 600; width: 45px;
}

/* Signal metrics */
.signal-metrics {
  display: flex; gap: 1px; background: #F0F0F0;
  margin: 0 20px;
}
.signal-metric {
  flex: 1; background: #fff; padding: 16px; text-align: center;
}
.metric-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.3rem; font-weight: 700; margin-bottom: 4px;
}
.metric-val.signal-buy-yes { color: #10B981; }
.metric-val.signal-buy-no { color: #dc2626; }
.metric-val.signal-hold { color: #999; }
.metric-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem; color: #BBB; text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Reasoning */
.signal-reasoning {
  padding: 16px 20px;
  font-size: 0.85rem; color: #666; line-height: 1.6;
  border-top: 1px solid #F5F5F5;
}

/* ═══════ SENTIMENT ═══════ */
.sentiment-section { padding: 0 20px 20px; }
.sentiment-head {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem; color: #999; text-transform: uppercase;
  letter-spacing: 0.5px; margin-bottom: 12px;
  padding-top: 16px; border-top: 1px solid #F5F5F5;
}
.stance-bar-wrap {
  display: flex; height: 6px; overflow: hidden; margin-bottom: 10px;
  gap: 1px;
}
.stance-bar { transition: width 0.5s ease; }
.for-bar { background: #10B981; }
.neutral-bar { background: #E5E5E5; }
.against-bar { background: #dc2626; }
.stance-legend {
  display: flex; gap: 16px; margin-bottom: 16px;
  font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;
}
.stance-item { display: flex; align-items: center; gap: 5px; color: #666; }
.stance-dot { width: 6px; height: 6px; display: inline-block; }
.for-dot { background: #10B981; }
.neutral-dot { background: #E5E5E5; }
.against-dot { background: #dc2626; }

/* Arguments */
.args-block { margin-bottom: 12px; }
.args-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; font-weight: 600;
  margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;
}
.for-title { color: #10B981; }
.against-title { color: #dc2626; }
.arg-item {
  display: flex; align-items: flex-start; gap: 8px;
  font-size: 0.82rem; color: #666; line-height: 1.5;
  margin-bottom: 6px; padding-left: 4px;
}
.arg-bullet {
  width: 4px; height: 4px; margin-top: 7px; flex-shrink: 0;
}
.for-bullet { background: #10B981; }
.against-bullet { background: #dc2626; }

/* ═══════ FAILED ═══════ */
.panel-failed { border-color: #FEE2E2; }
.failed-msg {
  padding: 16px 20px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem; color: #dc2626; line-height: 1.5;
}

/* ═══════ HISTORY ═══════ */
.pred-history {
  max-height: 350px; overflow-y: auto;
  scrollbar-width: thin; scrollbar-color: #DDD #F5F5F5;
}
.history-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 20px; border-bottom: 1px solid #F5F5F5;
  cursor: pointer; transition: background 0.15s;
  gap: 12px;
}
.history-row:hover { background: #FAFAFA; }
.history-row.active { background: #FFF8F5; }
.history-left { flex: 1; min-width: 0; }
.history-title {
  font-size: 0.85rem; font-weight: 500; line-height: 1.3;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.history-date {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem; color: #CCC; margin-top: 3px;
}
.history-right {
  display: flex; align-items: center; gap: 8px; flex-shrink: 0;
}
.history-status {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
  padding: 2px 8px; letter-spacing: 0.5px;
}
.status-completed { color: #10B981; background: #ECFDF5; }
.status-failed { color: #dc2626; background: #FEF2F2; }
.status-running_simulation, .status-analyzing, .status-building_graph,
.status-preparing_simulation, .status-generating_scenario, .status-creating_project,
.status-fetching_market { color: #FF4500; background: #FFF5F0; }
.history-signal {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; font-weight: 600;
  display: flex; align-items: center; gap: 4px;
}
.history-signal.signal-buy-yes { color: #10B981; }
.history-signal.signal-buy-no { color: #dc2626; }
.history-signal.signal-hold { color: #999; }
.history-edge { opacity: 0.7; }

/* ═══════ TRANSITIONS ═══════ */
.panel-slide-enter-active { animation: panelIn 0.35s cubic-bezier(0.23, 1, 0.32, 1); }
.panel-slide-leave-active { animation: panelOut 0.2s ease-in forwards; }

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
@keyframes panelIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes panelOut {
  from { opacity: 1; transform: translateY(0); }
  to { opacity: 0; transform: translateY(-10px); }
}

/* ═══════ RESPONSIVE ═══════ */
@media (max-width: 1024px) {
  .pred-grid { grid-template-columns: 1fr; }
  .pred-col-left { order: 1; }
  .pred-col-right { order: 2; }
  .pred-main { padding: 20px; }
  .pred-nav { padding: 0 20px; }
  .pred-hero-inner { padding: 12px 20px; }
  .pred-hero-left { display: none; }
}
@media (max-width: 768px) {
  .pred-nav-center { display: none; }
  .pred-hero-right { gap: 16px; }
  .selected-stats { flex-direction: column; }
  .signal-metrics { flex-direction: column; gap: 0; }
}
</style>
