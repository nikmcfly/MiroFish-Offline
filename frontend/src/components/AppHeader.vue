<template>
  <header class="app-header">
    <div class="header-left">
      <button class="brand" type="button" @click="goHome">{{ brand.displayName }}</button>
    </div>

    <div class="header-center">
      <div class="view-switcher" role="group" aria-label="Workspace view">
        <button
          v-for="mode in viewModes"
          :key="mode"
          class="switch-btn"
          :class="{ active: viewMode === mode }"
          type="button"
          @click="$emit('update:viewMode', mode)"
        >
          {{ viewModeLabels[mode] }}
        </button>
      </div>
    </div>

    <div class="header-right">
      <div class="workflow-step">
        <span class="step-num">Step {{ step }}/5</span>
        <span class="step-name">{{ stepName }}</span>
      </div>
      <div class="step-divider"></div>
      <span class="status-indicator" :class="statusClass">
        <span class="dot"></span>
        {{ statusText }}
      </span>
    </div>
  </header>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { brand } from '../brand'

defineProps({
  step: {
    type: Number,
    required: true
  },
  stepName: {
    type: String,
    required: true
  },
  statusClass: {
    type: String,
    default: 'processing'
  },
  statusText: {
    type: String,
    default: 'Ready'
  },
  viewMode: {
    type: String,
    default: 'split'
  }
})

defineEmits(['update:viewMode'])

const router = useRouter()
const viewModes = ['graph', 'split', 'workbench']
const viewModeLabels = { graph: 'Graph', split: 'Split', workbench: 'Workbench' }

const goHome = () => {
  router.push('/')
}
</script>

<style scoped>
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
  font-family: var(--font-mono);
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 1px;
  cursor: pointer;
  color: #000;
  background: transparent;
  border: 0;
  padding: 0;
}

.brand:focus-visible,
.switch-btn:focus-visible {
  outline: 2px solid var(--brand-accent);
  outline-offset: 2px;
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
  font-family: var(--font-mono);
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

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #CCC;
}

.status-indicator.ready .dot,
.status-indicator.completed .dot {
  background: #4CAF50;
}

.status-indicator.processing .dot {
  background: var(--brand-accent);
  animation: pulse 1s infinite;
}

.status-indicator.error .dot {
  background: #F44336;
}

@keyframes pulse {
  50% {
    opacity: 0.5;
  }
}
</style>
