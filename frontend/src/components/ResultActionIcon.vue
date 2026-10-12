<script setup lang="ts">
defineProps<{ kind: 'download' | 'visualize' | 'clear' }>()
</script>

<template>
  <svg class="result-action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <template v-if="kind === 'download'">
      <path d="M12 3v12m-5-5 5 5 5-5" />
      <path d="M3 16v4a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1v-4" />
    </template>
    <template v-else-if="kind === 'visualize'">
      <path d="M12 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v7" />
      <circle cx="17.5" cy="17.5" r="3.5" />
      <path d="m20 20 2 2" />
    </template>
    <g v-else stroke-linecap="square" stroke-linejoin="miter">
      <path d="M8 6V3h8v3M4 6h16M6 7l1 14h10l1-14" />
      <path d="M10 17h4" stroke-linecap="butt" />
    </g>
  </svg>
</template>
