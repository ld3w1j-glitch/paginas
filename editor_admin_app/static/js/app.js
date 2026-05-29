const STORAGE_KEY = 'figma_like_editor_v17';

const defaultState = () => ({
  page: {
    width: 1440,
    height: 900,
    bg: '#ffffff',
    gridSize: 16,
    showGrid: true,
    snap: true
  },
  zoom: 1,
  elements: [],
  guides: {
    vertical: [],
    horizontal: []
  },
  selectedIds: [],
  selectedGuide: null
});

let state = loadState();
let interaction = null;
let historyStack = [];
let redoStack = [];
let isApplyingHistory = false;

const els = {
  artboard: document.getElementById('artboard'),
  artboardWrap: document.getElementById('artboardWrap'),
  workspaceStage: document.getElementById('workspaceStage'),
  layersList: document.getElementById('layersList'),
  zoomLabel: document.getElementById('zoomLabel'),
  selectionLabel: document.getElementById('selectionLabel'),
  pageWidth: document.getElementById('pageWidth'),
  pageHeight: document.getElementById('pageHeight'),
  pageBg: document.getElementById('pageBg'),
  gridSize: document.getElementById('gridSize'),
  snapToggle: document.getElementById('snapToggle'),
  showGridToggle: document.getElementById('showGridToggle'),
  propsPanel: document.getElementById('propsPanel'),
  emptyStateBox: document.getElementById('emptyStateBox'),
  multiStateBox: document.getElementById('multiStateBox'),
  guideStateBox: document.getElementById('guideStateBox'),
  topRulerInner: document.getElementById('topRulerInner'),
  leftRulerInner: document.getElementById('leftRulerInner'),
  rulerTop: document.getElementById('rulerTop'),
  rulerLeft: document.getElementById('rulerLeft'),
  propName: document.getElementById('propName'),
  propX: document.getElementById('propX'),
  propY: document.getElementById('propY'),
  propW: document.getElementById('propW'),
  propH: document.getElementById('propH'),
  propRotate: document.getElementById('propRotate'),
  propOpacity: document.getElementById('propOpacity'),
  propRadius: document.getElementById('propRadius'),
  propFill: document.getElementById('propFill'),
  propFillOpacity: document.getElementById('propFillOpacity'),
  propFillMode: document.getElementById('propFillMode'),
  propGradientType: document.getElementById('propGradientType'),
  propGradientColorA: document.getElementById('propGradientColorA'),
  propGradientOpacityA: document.getElementById('propGradientOpacityA'),
  propGradientColorB: document.getElementById('propGradientColorB'),
  propGradientOpacityB: document.getElementById('propGradientOpacityB'),
  propGradientAngle: document.getElementById('propGradientAngle'),
  propStroke: document.getElementById('propStroke'),
  propStrokeOpacity: document.getElementById('propStrokeOpacity'),
  propStrokeWidth: document.getElementById('propStrokeWidth'),
  propFontSize: document.getElementById('propFontSize'),
  propFontWeight: document.getElementById('propFontWeight'),
  propText: document.getElementById('propText'),
  jsonImportInput: document.getElementById('jsonImportInput'),
  imageImportInput: document.getElementById('imageImportInput')
};

const propMap = {
  propName: 'name',
  propX: 'x',
  propY: 'y',
  propW: 'w',
  propH: 'h',
  propRotate: 'rotate',
  propOpacity: 'opacity',
  propRadius: 'radius',
  propFill: 'fill',
  propFillOpacity: 'fillOpacity',
  propFillMode: 'fillMode',
  propGradientType: 'gradientType',
  propGradientColorA: 'gradientColorA',
  propGradientOpacityA: 'gradientOpacityA',
  propGradientColorB: 'gradientColorB',
  propGradientOpacityB: 'gradientOpacityB',
  propGradientAngle: 'gradientAngle',
  propStroke: 'stroke',
  propStrokeOpacity: 'strokeOpacity',
  propStrokeWidth: 'strokeWidth',
  propFontSize: 'fontSize',
  propFontWeight: 'fontWeight',
  propText: 'text'
};

init();

function init() {
  document.querySelectorAll('[data-add]').forEach((btn) => {
    btn.addEventListener('click', () => handleAdd(btn.dataset.add));
  });

  document.querySelectorAll('[data-action]').forEach((btn) => {
    btn.addEventListener('click', () => handleAction(btn.dataset.action));
  });

  Object.keys(propMap).forEach((id) => {
    const input = els[id];
    input.addEventListener('input', () => {
      const selected = getSingleSelected();
      if (!selected) return;
      const key = propMap[id];
      let value = input.value;
      if (['x', 'y', 'w', 'h', 'rotate', 'opacity', 'radius', 'strokeWidth', 'fontSize', 'fontWeight', 'fillOpacity', 'strokeOpacity', 'gradientOpacityA', 'gradientOpacityB', 'gradientAngle'].includes(key)) {
        value = Number(value);
        if (Number.isNaN(value)) value = 0;
      }
      if (key === 'w' || key === 'h') value = Math.max(10, value);
      if (key === 'opacity' || key === 'fillOpacity' || key === 'strokeOpacity' || key === 'gradientOpacityA' || key === 'gradientOpacityB') value = clamp(value, 0, 1);
      if (key === 'radius') value = Math.max(0, value);
      if (key === 'fontSize') value = Math.max(8, value);
      if (key === 'gradientAngle') value = Number.isFinite(value) ? value : 0;

      if (key === 'x' || key === 'y') {
        const abs = getAbsolutePosition(selected);
        const nextAbsX = key === 'x' ? value : abs.x;
        const nextAbsY = key === 'y' ? value : abs.y;
        setAbsolutePosition(selected, nextAbsX, nextAbsY);
      } else {
        selected[key] = value;
      }
      render();
      persist();
    });
  });

  [els.pageWidth, els.pageHeight, els.gridSize].forEach((input) => {
    input.addEventListener('input', () => {
      const value = Math.max(input === els.gridSize ? 2 : 320, Number(input.value) || (input === els.gridSize ? 16 : 320));
      if (input === els.pageWidth) state.page.width = value;
      if (input === els.pageHeight) state.page.height = value;
      if (input === els.gridSize) state.page.gridSize = Math.max(2, value);
      render();
      persist();
    });
  });

  els.pageBg.addEventListener('input', () => {
    state.page.bg = els.pageBg.value;
    render();
    persist();
  });

  els.snapToggle.addEventListener('change', () => {
    state.page.snap = els.snapToggle.checked;
    persist();
    render();
  });

  els.showGridToggle.addEventListener('change', () => {
    state.page.showGrid = els.showGridToggle.checked;
    persist();
    render();
  });

  els.artboard.addEventListener('pointerdown', onArtboardPointerDown);
  els.rulerTop.addEventListener('pointerdown', (event) => startGuideCreate(event, 'vertical'));
  els.rulerLeft.addEventListener('pointerdown', (event) => startGuideCreate(event, 'horizontal'));
  document.addEventListener('keydown', handleKeyboard);
  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  els.workspaceStage.addEventListener('scroll', syncRulerOffset);
  els.workspaceStage.addEventListener('wheel', handleStageWheel, { passive: false });

  els.jsonImportInput.addEventListener('change', importJsonFile);
  els.imageImportInput.addEventListener('change', importImageFile);

  render();
  initHistory();
}


function handleAction(action) {
  switch (action) {
    case 'new-project':
      if (confirm('Quer começar um projeto novo em branco?')) {
        state = defaultState();
        persist();
        render();
      }
      break;
    case 'save-project':
      persist();
      alert('Projeto salvo no navegador.');
      break;
    case 'undo':
      undoHistory();
      break;
    case 'redo':
      redoHistory();
      break;
    case 'export-json':
      downloadFile('editor_visual_v16.json', JSON.stringify(state, null, 2), 'application/json');
      break;
    case 'import-json':
      els.jsonImportInput.value = '';
      els.jsonImportInput.click();
      break;
    case 'export-html':
      exportHtml();
      break;
    case 'duplicate-selected':
      duplicateSelected();
      break;
    case 'delete-selected':
      deleteSelected();
      break;
    case 'bring-forward':
      moveSelected(1);
      break;
    case 'send-backward':
      moveSelected(-1);
      break;
    case 'zoom-in':
      setZoom(state.zoom + 0.1);
      break;
    case 'zoom-out':
      setZoom(state.zoom - 0.1);
      break;
    case 'zoom-reset':
      setZoom(1);
      break;
    case 'align-left':
      alignSelected('left');
      break;
    case 'align-h-center':
      alignSelected('h-center');
      break;
    case 'align-right':
      alignSelected('right');
      break;
    case 'align-top':
      alignSelected('top');
      break;
    case 'align-v-center':
      alignSelected('v-center');
      break;
    case 'align-bottom':
      alignSelected('bottom');
      break;
    case 'distribute-horizontal':
      distributeSelected('horizontal');
      break;
    case 'distribute-vertical':
      distributeSelected('vertical');
      break;
    case 'clear-guides':
      state.guides = { vertical: [], horizontal: [] };
      state.selectedGuide = null;
      render();
      persist();
      break;
  }
}

function handleAdd(type) {
  if (type === 'image') {
    els.imageImportInput.value = '';
    els.imageImportInput.click();
    return;
  }
  const parentId = getSelectedFrameId();
  const element = createElement(type, parentId);
  state.elements.push(element);
  state.selectedIds = [element.id];
  state.selectedGuide = null;
  render();
  persist();
}

function createElement(type, parentId = null, extra = {}) {
  const base = {
    id: `el_${Math.random().toString(36).slice(2, 10)}`,
    type,
    name: getDefaultName(type),
    parentId,
    x: 120,
    y: 100,
    w: 240,
    h: 120,
    fill: '#d9e7ff',
    fillOpacity: 1,
    fillMode: 'solid',
    gradientType: 'linear',
    gradientColorA: '#d9e7ff',
    gradientOpacityA: 1,
    gradientColorB: '#4c8dff',
    gradientOpacityB: 1,
    gradientAngle: 135,
    stroke: '#4c8dff',
    strokeOpacity: 1,
    strokeWidth: 1,
    radius: 18,
    opacity: 1,
    rotate: 0,
    text: '',
    fontSize: 24,
    fontWeight: 600,
    src: ''
  };

  if (parentId) {
    base.x = 24;
    base.y = 24;
  }
  if (type === 'frame') {
    Object.assign(base, { w: 420, h: 280, fill: '#f7f8fd', gradientColorA: '#f7f8fd', gradientColorB: '#dbe4ff', stroke: '#91a0b7', radius: 24, name: 'Frame' });
  }
  if (type === 'circle') {
    Object.assign(base, { w: 140, h: 140, radius: 999, fill: '#ffd6b3', gradientColorA: '#ffd6b3', gradientColorB: '#ff934d', stroke: '#ff934d' });
  }
  if (type === 'text') {
    Object.assign(base, { w: 320, h: 64, fill: '#222222', gradientColorA: '#222222', gradientColorB: '#4c8dff', stroke: '#222222', strokeWidth: 0, radius: 0, text: 'Novo texto', fontSize: 36, fontWeight: 700 });
  }
  if (type === 'button') {
    Object.assign(base, { w: 220, h: 56, fill: '#111111', gradientColorA: '#111111', gradientColorB: '#4c8dff', stroke: '#111111', strokeWidth: 0, radius: 999, text: 'Clique aqui', fontSize: 18, fontWeight: 600 });
  }
  if (type === 'rect') {
    Object.assign(base, { text: '' });
  }
  if (type === 'image') {
    Object.assign(base, { w: 260, h: 180, fill: '#f1f1f1', stroke: '#d0d0d0', text: '', radius: 16 });
  }
  return { ...base, ...extra };
}

function getDefaultName(type) {
  const map = {
    frame: 'Frame',
    rect: 'Retângulo',
    circle: 'Círculo',
    text: 'Texto',
    button: 'Botão',
    image: 'Imagem'
  };
  return map[type] || 'Elemento';
}

function render() {
  ensureGuideState();
  renderArtboard();
  renderLayers();
  renderProps();
  renderPageControls();
  renderZoom();
  renderRulers();
  syncRulerOffset();
}

function ensureGuideState() {
  state.guides = state.guides || { vertical: [], horizontal: [] };
  state.guides.vertical = Array.isArray(state.guides.vertical) ? state.guides.vertical.map((value) => clamp(Number(value) || 0, 0, state.page.width)) : [];
  state.guides.horizontal = Array.isArray(state.guides.horizontal) ? state.guides.horizontal.map((value) => clamp(Number(value) || 0, 0, state.page.height)) : [];
}

function renderArtboard() {
  els.artboard.style.width = `${state.page.width}px`;
  els.artboard.style.height = `${state.page.height}px`;
  els.artboard.style.background = state.page.bg;
  els.artboardWrap.style.transform = `scale(${state.zoom})`;
  els.workspaceStage.classList.toggle('show-grid', !!state.page.showGrid);
  els.workspaceStage.style.backgroundSize = `${state.page.gridSize}px ${state.page.gridSize}px`;
  els.artboard.innerHTML = '';

  if (!state.elements.length) {
    const empty = document.createElement('div');
    empty.className = 'artboard-empty';
    empty.textContent = 'Página em branco. Use as ferramentas da esquerda para começar.';
    els.artboard.appendChild(empty);
  }

  renderPermanentGuides();
  renderChildren(els.artboard, null);

  if (interaction?.mode === 'select-box') {
    const box = document.createElement('div');
    box.className = 'selection-box';
    const rect = getSelectionRect(interaction);
    box.style.left = `${rect.x}px`;
    box.style.top = `${rect.y}px`;
    box.style.width = `${rect.w}px`;
    box.style.height = `${rect.h}px`;
    els.artboard.appendChild(box);
  }

  const snapLines = interaction?.snapLines || { vertical: [], horizontal: [] };
  snapLines.vertical.forEach((x) => {
    const guide = document.createElement('div');
    guide.className = 'guide-line temporary vertical';
    guide.style.left = `${x}px`;
    els.artboard.appendChild(guide);
  });
  snapLines.horizontal.forEach((y) => {
    const guide = document.createElement('div');
    guide.className = 'guide-line temporary horizontal';
    guide.style.top = `${y}px`;
    els.artboard.appendChild(guide);
  });
}

function renderPermanentGuides() {
  state.guides.vertical.forEach((x, index) => {
    const guide = document.createElement('div');
    guide.className = 'guide-line permanent vertical';
    if (state.selectedGuide && state.selectedGuide.orientation === 'vertical' && state.selectedGuide.index === index) {
      guide.classList.add('active');
    }
    guide.style.left = `${x}px`;
    guide.addEventListener('pointerdown', (event) => startGuideMove(event, 'vertical', index));
    els.artboard.appendChild(guide);
  });

  state.guides.horizontal.forEach((y, index) => {
    const guide = document.createElement('div');
    guide.className = 'guide-line permanent horizontal';
    if (state.selectedGuide && state.selectedGuide.orientation === 'horizontal' && state.selectedGuide.index === index) {
      guide.classList.add('active');
    }
    guide.style.top = `${y}px`;
    guide.addEventListener('pointerdown', (event) => startGuideMove(event, 'horizontal', index));
    els.artboard.appendChild(guide);
  });
}

function renderChildren(parentContainer, parentId) {
  getChildren(parentId).forEach((element) => {
    const node = document.createElement('div');
    node.className = `canvas-element ${element.type === 'frame' ? 'frame-element' : ''}`;
    if (isSelected(element.id)) {
      node.classList.add(state.selectedIds.length > 1 ? 'multi' : 'selected');
    }
    node.dataset.id = element.id;
    node.style.left = `${element.x}px`;
    node.style.top = `${element.y}px`;
    node.style.width = `${element.w}px`;
    node.style.height = `${element.h}px`;
    node.style.opacity = String(element.opacity ?? 1);
    node.style.transform = `rotate(${element.rotate || 0}deg)`;

    const content = document.createElement('div');
    content.className = `element-content type-${element.type}`;
    applyElementVisualStyles(content, element);

    if (element.type === 'text') {
      content.style.fontSize = `${element.fontSize || 16}px`;
      content.style.fontWeight = String(element.fontWeight || 400);
      content.textContent = element.text || 'Novo texto';
    } else if (element.type === 'button') {
      content.style.fontSize = `${element.fontSize || 16}px`;
      content.style.fontWeight = String(element.fontWeight || 600);
      content.style.color = '#ffffff';
      content.textContent = element.text || 'Clique aqui';
    } else if (element.type === 'image') {
      if (element.src) {
        const img = document.createElement('img');
        img.src = element.src;
        img.alt = element.name || 'Imagem';
        content.appendChild(img);
      } else {
        content.style.color = '#5f6773';
        content.style.fontSize = '14px';
        content.textContent = 'Imagem';
      }
    }

    if (element.type === 'text' || element.type === 'button') {
      content.addEventListener('dblclick', (event) => {
        event.preventDefault();
        event.stopPropagation();
        startInlineTextEdit(element.id);
      });
    }

    node.appendChild(content);

    if (element.type === 'frame') {
      const label = document.createElement('div');
      label.className = 'frame-label';
      label.textContent = element.name || 'Frame';
      node.appendChild(label);

      const childrenBox = document.createElement('div');
      childrenBox.className = 'frame-children';
      renderChildren(childrenBox, element.id);
      node.appendChild(childrenBox);
    }

    node.addEventListener('pointerdown', (event) => startNodeInteraction(event, element.id));

    if (isSelected(element.id) && state.selectedIds.length === 1) {
      const handle = document.createElement('div');
      handle.className = 'resize-handle';
      handle.addEventListener('pointerdown', (event) => startResize(event, element.id));
      node.appendChild(handle);
    }

    parentContainer.appendChild(node);
  });
}

function renderLayers() {
  els.layersList.innerHTML = '';
  if (!state.elements.length) {
    const div = document.createElement('div');
    div.className = 'layer-empty';
    div.textContent = 'Ainda não existe nenhuma camada.';
    els.layersList.appendChild(div);
    return;
  }

  const ordered = buildLayerTree(null, 0).reverse();
  ordered.forEach(({ element, level }) => {
    const button = document.createElement('button');
    button.className = 'layer-item';
    if (isSelected(element.id)) button.classList.add('active');
    button.style.paddingLeft = `${12 + level * 16}px`;
    button.addEventListener('click', (event) => {
      state.selectedGuide = null;
      if (event.shiftKey) toggleSelection(element.id);
      else state.selectedIds = [element.id];
      render();
      persist();
    });

    const meta = document.createElement('div');
    meta.className = 'layer-meta';
    meta.innerHTML = `<span class="layer-name">${escapeHtml(element.name || getDefaultName(element.type))}</span><span class="layer-type">${escapeHtml(element.type)}</span>`;

    const size = document.createElement('span');
    size.className = 'layer-type';
    size.textContent = `${Math.round(element.w)}×${Math.round(element.h)}`;

    button.appendChild(meta);
    button.appendChild(size);
    els.layersList.appendChild(button);
  });
}

function buildLayerTree(parentId, level) {
  let result = [];
  getChildren(parentId).forEach((element) => {
    result.push({ element, level });
    result = result.concat(buildLayerTree(element.id, level + 1));
  });
  return result;
}

function renderProps() {
  const selected = getSingleSelected();
  const guideSelected = !!state.selectedGuide;

  if (guideSelected) {
    els.propsPanel.classList.add('hidden');
    els.emptyStateBox.classList.add('hidden');
    els.multiStateBox.classList.add('hidden');
    els.guideStateBox.classList.remove('hidden');
    const label = state.selectedGuide.orientation === 'vertical' ? 'Guia vertical' : 'Guia horizontal';
    els.selectionLabel.textContent = `${label} selecionada`;
    return;
  }

  els.guideStateBox.classList.add('hidden');

  if (!state.selectedIds.length) {
    els.propsPanel.classList.add('hidden');
    els.emptyStateBox.classList.remove('hidden');
    els.multiStateBox.classList.add('hidden');
    els.selectionLabel.textContent = 'Nenhum elemento selecionado';
    return;
  }
  if (!selected) {
    els.propsPanel.classList.add('hidden');
    els.emptyStateBox.classList.add('hidden');
    els.multiStateBox.classList.remove('hidden');
    els.selectionLabel.textContent = `${state.selectedIds.length} elementos selecionados`;
    return;
  }

  els.propsPanel.classList.remove('hidden');
  els.emptyStateBox.classList.add('hidden');
  els.multiStateBox.classList.add('hidden');
  els.selectionLabel.textContent = `${selected.name} · ${selected.type}`;

  const abs = getAbsolutePosition(selected);
  els.propName.value = selected.name || '';
  els.propX.value = Math.round(abs.x);
  els.propY.value = Math.round(abs.y);
  els.propW.value = Math.round(selected.w);
  els.propH.value = Math.round(selected.h);
  els.propRotate.value = Math.round(selected.rotate || 0);
  els.propOpacity.value = selected.opacity ?? 1;
  els.propRadius.value = Math.round(selected.radius || 0);
  els.propFill.value = normalizeColor(selected.fill || '#000000');
  els.propFillOpacity.value = selected.fillOpacity ?? 1;
  els.propFillMode.value = selected.fillMode || 'solid';
  els.propGradientType.value = selected.gradientType || 'linear';
  els.propGradientColorA.value = normalizeColor(selected.gradientColorA || selected.fill || '#000000');
  els.propGradientOpacityA.value = selected.gradientOpacityA ?? 1;
  els.propGradientColorB.value = normalizeColor(selected.gradientColorB || selected.stroke || '#000000');
  els.propGradientOpacityB.value = selected.gradientOpacityB ?? 1;
  els.propGradientAngle.value = Math.round(selected.gradientAngle || 0);
  els.propStroke.value = normalizeColor(selected.stroke || '#000000');
  els.propStrokeOpacity.value = selected.strokeOpacity ?? 1;
  els.propStrokeWidth.value = Math.round(selected.strokeWidth || 0);
  els.propFontSize.value = Math.round(selected.fontSize || 16);
  els.propFontWeight.value = String(selected.fontWeight || 400);
  els.propText.value = selected.text || '';
}

function renderPageControls() {
  els.pageWidth.value = state.page.width;
  els.pageHeight.value = state.page.height;
  els.pageBg.value = normalizeColor(state.page.bg || '#ffffff');
  els.gridSize.value = state.page.gridSize;
  els.snapToggle.checked = !!state.page.snap;
  els.showGridToggle.checked = !!state.page.showGrid;
}

function renderZoom() {
  els.zoomLabel.textContent = `${Math.round(state.zoom * 100)}%`;
}

function renderRulers() {
  els.topRulerInner.innerHTML = '';
  els.leftRulerInner.innerHTML = '';
  const step = 50;
  const width = state.page.width * state.zoom;
  const height = state.page.height * state.zoom;
  els.topRulerInner.style.width = `${Math.max(width, els.workspaceStage.clientWidth)}px`;
  els.leftRulerInner.style.height = `${Math.max(height, els.workspaceStage.clientHeight)}px`;

  for (let x = 0; x <= state.page.width; x += step) {
    const tick = document.createElement('div');
    tick.className = 'ruler-tick';
    tick.style.left = `${x * state.zoom}px`;
    tick.textContent = String(x);
    els.topRulerInner.appendChild(tick);
  }
  for (let y = 0; y <= state.page.height; y += step) {
    const tick = document.createElement('div');
    tick.className = 'ruler-tick';
    tick.style.top = `${y * state.zoom}px`;
    tick.textContent = String(y);
    els.leftRulerInner.appendChild(tick);
  }
}

function syncRulerOffset() {
  els.topRulerInner.style.transform = `translateX(${-els.workspaceStage.scrollLeft}px)`;
  els.leftRulerInner.style.transform = `translateY(${-els.workspaceStage.scrollTop}px)`;
}

function onArtboardPointerDown(event) {
  if (event.target.closest('.is-editing')) return;
  if (!event.target.closest('.artboard') || event.target.classList.contains('guide-line') || event.target.closest('.canvas-element')) return;
  const point = toArtboardPoint(event);
  interaction = {
    mode: 'select-box',
    startX: point.x,
    startY: point.y,
    currentX: point.x,
    currentY: point.y,
    additive: event.shiftKey,
    snapLines: { vertical: [], horizontal: [] }
  };
  state.selectedGuide = null;
  if (!event.shiftKey) state.selectedIds = [];
  render();
}

function startGuideCreate(event, orientation) {
  event.preventDefault();
  event.stopPropagation();
  state.selectedIds = [];
  const point = toArtboardPoint(event);
  const list = state.guides[orientation];
  const value = orientation === 'vertical' ? point.x : point.y;
  list.push(orientation === 'vertical' ? clamp(snapValue(value), 0, state.page.width) : clamp(snapValue(value), 0, state.page.height));
  const index = list.length - 1;
  state.selectedGuide = { orientation, index };
  interaction = {
    mode: 'move-guide',
    orientation,
    index,
    snapLines: { vertical: orientation === 'vertical' ? [list[index]] : [], horizontal: orientation === 'horizontal' ? [list[index]] : [] }
  };
  render();
}

function startGuideMove(event, orientation, index) {
  event.preventDefault();
  event.stopPropagation();
  state.selectedIds = [];
  state.selectedGuide = { orientation, index };
  interaction = {
    mode: 'move-guide',
    orientation,
    index,
    snapLines: { vertical: orientation === 'vertical' ? [state.guides.vertical[index]] : [], horizontal: orientation === 'horizontal' ? [state.guides.horizontal[index]] : [] }
  };
  render();
}

function startNodeInteraction(event, id) {
  if (event.target.classList.contains('resize-handle') || event.target.closest('.is-editing')) return;
  const target = getElementById(id);
  if (!target) return;
  event.preventDefault();
  event.stopPropagation();

  state.selectedGuide = null;
  if (event.shiftKey) {
    toggleSelection(id);
  } else if (!isSelected(id)) {
    state.selectedIds = [id];
  }

  const ids = state.selectedIds.length ? [...state.selectedIds] : [id];
  interaction = {
    mode: 'drag',
    ids,
    startX: event.clientX,
    startY: event.clientY,
    origins: ids.map((selId) => {
      const element = getElementById(selId);
      const abs = getAbsolutePosition(element);
      return { id: selId, absX: abs.x, absY: abs.y };
    }),
    groupBounds: getGroupBounds(ids),
    snapLines: { vertical: [], horizontal: [] }
  };
  render();
}

function startResize(event, id) {
  const target = getElementById(id);
  if (!target) return;
  event.preventDefault();
  event.stopPropagation();
  state.selectedGuide = null;
  state.selectedIds = [id];
  const abs = getAbsolutePosition(target);
  interaction = {
    mode: 'resize',
    id,
    startX: event.clientX,
    startY: event.clientY,
    originW: target.w,
    originH: target.h,
    originAbsX: abs.x,
    originAbsY: abs.y,
    keepCircle: target.type === 'circle',
    snapLines: { vertical: [], horizontal: [] }
  };
  render();
}

function onPointerMove(event) {
  if (!interaction) return;

  if (interaction.mode === 'select-box') {
    const point = toArtboardPoint(event);
    interaction.currentX = point.x;
    interaction.currentY = point.y;
    render();
    return;
  }

  if (interaction.mode === 'move-guide') {
    const point = toArtboardPoint(event);
    if (interaction.orientation === 'vertical') {
      const value = clamp(snapValue(point.x), -200, state.page.width + 200);
      state.guides.vertical[interaction.index] = value;
      interaction.snapLines = { vertical: [clamp(value, 0, state.page.width)], horizontal: [] };
    } else {
      const value = clamp(snapValue(point.y), -200, state.page.height + 200);
      state.guides.horizontal[interaction.index] = value;
      interaction.snapLines = { vertical: [], horizontal: [clamp(value, 0, state.page.height)] };
    }
    render();
    return;
  }

  if (interaction.mode === 'drag') {
    const rawDx = (event.clientX - interaction.startX) / state.zoom;
    const rawDy = (event.clientY - interaction.startY) / state.zoom;
    const snapped = getDragSnap(rawDx, rawDy, interaction.ids, interaction.groupBounds);
    interaction.snapLines = snapped.lines;

    interaction.origins.forEach((origin) => {
      const target = getElementById(origin.id);
      if (!target) return;
      const nextAbsX = origin.absX + snapped.dx;
      const nextAbsY = origin.absY + snapped.dy;
      const reparent = findTargetFrame(origin.id, nextAbsX + target.w / 2, nextAbsY + target.h / 2);
      if (reparent) {
        target.parentId = reparent.id;
      } else {
        target.parentId = null;
      }
      setAbsolutePosition(target, nextAbsX, nextAbsY);
    });
    render();
    return;
  }

  if (interaction.mode === 'resize') {
    const target = getElementById(interaction.id);
    if (!target) return;
    const dx = (event.clientX - interaction.startX) / state.zoom;
    const dy = (event.clientY - interaction.startY) / state.zoom;
    let nextW = Math.max(20, interaction.originW + dx);
    let nextH = Math.max(20, interaction.originH + dy);

    if (state.page.snap) {
      nextW = snapValue(nextW);
      nextH = snapValue(nextH);
    }

    const resizeSnap = getResizeSnap(interaction.id, interaction.originAbsX, interaction.originAbsY, nextW, nextH, interaction.keepCircle);
    interaction.snapLines = resizeSnap.lines;
    nextW = resizeSnap.w;
    nextH = resizeSnap.h;

    if (interaction.keepCircle) {
      const size = Math.max(nextW, nextH);
      target.w = size;
      target.h = size;
      target.radius = 999;
    } else {
      target.w = nextW;
      target.h = nextH;
    }
    render();
  }
}

function onPointerUp() {
  if (!interaction) return;
  if (interaction.mode === 'select-box') {
    const rect = getSelectionRect(interaction);
    const hits = state.elements.filter((element) => rectsIntersect(rect, getAbsoluteBounds(element))).map((item) => item.id);
    state.selectedGuide = null;
    state.selectedIds = interaction.additive ? unique([...state.selectedIds, ...hits]) : hits;
  }

  if (interaction.mode === 'move-guide') {
    const list = state.guides[interaction.orientation];
    const limit = interaction.orientation === 'vertical' ? state.page.width : state.page.height;
    if (list[interaction.index] < 0 || list[interaction.index] > limit) {
      list.splice(interaction.index, 1);
      state.selectedGuide = null;
    } else {
      list[interaction.index] = clamp(list[interaction.index], 0, limit);
      state.selectedGuide = { orientation: interaction.orientation, index: interaction.index };
    }
  }

  interaction = null;
  persist();
  render();
}

function handleKeyboard(event) {
  const tag = document.activeElement?.tagName;
  const editing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) || !!document.activeElement?.isContentEditable;

  if ((event.key === 'Delete' || event.key === 'Backspace') && !editing) {
    deleteSelected();
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z' && !editing) {
    event.preventDefault();
    if (event.shiftKey) redoHistory();
    else undoHistory();
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y' && !editing) {
    event.preventDefault();
    redoHistory();
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'd' && !editing) {
    event.preventDefault();
    duplicateSelected();
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a' && !editing) {
    event.preventDefault();
    state.selectedGuide = null;
    state.selectedIds = state.elements.map((item) => item.id);
    render();
    persist();
  }
  if (!editing && ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key) && state.selectedIds.length) {
    event.preventDefault();
    const step = event.shiftKey ? state.page.gridSize : 1;
    const deltaMap = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step]
    };
    const [dx, dy] = deltaMap[event.key];
    state.selectedIds.forEach((id) => moveElementBy(id, dx, dy));
    render();
    persist();
  }
}

function moveElementBy(id, dx, dy) {
  const element = getElementById(id);
  if (!element) return;
  const abs = getAbsolutePosition(element);
  setAbsolutePosition(element, abs.x + dx, abs.y + dy);
}

function duplicateSelected() {
  if (!state.selectedIds.length) return;
  state.selectedGuide = null;
  const newIds = [];
  const mapping = new Map();

  state.selectedIds.forEach((id) => {
    const selected = getElementById(id);
    if (!selected) return;
    const copy = JSON.parse(JSON.stringify(selected));
    const newId = `el_${Math.random().toString(36).slice(2, 10)}`;
    mapping.set(id, newId);
    copy.id = newId;
    copy.name = `${selected.name} cópia`;
    copy.x += 30;
    copy.y += 30;
    state.elements.push(copy);
    newIds.push(newId);
  });

  state.elements.forEach((element) => {
    if (mapping.has(element.parentId)) element.parentId = mapping.get(element.parentId);
  });

  state.selectedIds = newIds;
  render();
  persist();
}

function deleteSelected() {
  if (state.selectedGuide) {
    const { orientation, index } = state.selectedGuide;
    if (state.guides[orientation] && state.guides[orientation][index] != null) {
      state.guides[orientation].splice(index, 1);
    }
    state.selectedGuide = null;
    render();
    persist();
    return;
  }

  if (!state.selectedIds.length) return;
  const toDelete = new Set();
  state.selectedIds.forEach((id) => collectDescendants(id, toDelete));
  state.elements = state.elements.filter((item) => !toDelete.has(item.id));
  state.selectedIds = [];
  render();
  persist();
}

function collectDescendants(id, bucket) {
  bucket.add(id);
  state.elements.filter((item) => item.parentId === id).forEach((child) => collectDescendants(child.id, bucket));
}

function moveSelected(delta) {
  if (!state.selectedIds.length) return;
  const selectedSet = new Set(state.selectedIds);
  const orderedIds = delta > 0 ? [...state.elements].map((e) => e.id).reverse() : state.elements.map((e) => e.id);
  orderedIds.forEach((id) => {
    if (!selectedSet.has(id)) return;
    const index = state.elements.findIndex((item) => item.id === id);
    const nextIndex = clamp(index + delta, 0, state.elements.length - 1);
    if (nextIndex === index) return;
    const [item] = state.elements.splice(index, 1);
    state.elements.splice(nextIndex, 0, item);
  });
  render();
  persist();
}

function alignSelected(mode) {
  if (state.selectedIds.length < 2) return;
  const bounds = getGroupBounds(state.selectedIds);
  state.selectedIds.forEach((id) => {
    const element = getElementById(id);
    if (!element) return;
    const abs = getAbsolutePosition(element);
    let nextX = abs.x;
    let nextY = abs.y;

    if (mode === 'left') nextX = bounds.x;
    if (mode === 'h-center') nextX = bounds.x + bounds.w / 2 - element.w / 2;
    if (mode === 'right') nextX = bounds.x + bounds.w - element.w;
    if (mode === 'top') nextY = bounds.y;
    if (mode === 'v-center') nextY = bounds.y + bounds.h / 2 - element.h / 2;
    if (mode === 'bottom') nextY = bounds.y + bounds.h - element.h;

    setAbsolutePosition(element, nextX, nextY);
  });
  render();
  persist();
}

function distributeSelected(axis) {
  if (state.selectedIds.length < 3) return;
  const items = state.selectedIds
    .map((id) => getElementById(id))
    .filter(Boolean)
    .map((element) => ({ element, abs: getAbsolutePosition(element) }));
  if (items.length < 3) return;

  if (axis === 'horizontal') {
    items.sort((a, b) => a.abs.x - b.abs.x);
    const start = items[0].abs.x;
    const end = items[items.length - 1].abs.x + items[items.length - 1].element.w;
    const total = items.reduce((sum, item) => sum + item.element.w, 0);
    const gap = (end - start - total) / (items.length - 1);
    let cursor = start;
    items.forEach((item, index) => {
      if (index === 0) {
        cursor += item.element.w + gap;
        return;
      }
      if (index === items.length - 1) return;
      setAbsolutePosition(item.element, cursor, item.abs.y);
      cursor += item.element.w + gap;
    });
  } else {
    items.sort((a, b) => a.abs.y - b.abs.y);
    const start = items[0].abs.y;
    const end = items[items.length - 1].abs.y + items[items.length - 1].element.h;
    const total = items.reduce((sum, item) => sum + item.element.h, 0);
    const gap = (end - start - total) / (items.length - 1);
    let cursor = start;
    items.forEach((item, index) => {
      if (index === 0) {
        cursor += item.element.h + gap;
        return;
      }
      if (index === items.length - 1) return;
      setAbsolutePosition(item.element, item.abs.x, cursor);
      cursor += item.element.h + gap;
    });
  }

  render();
  persist();
}

function setZoom(value) {
  state.zoom = clamp(Number(value) || 1, 0.3, 2);
  render();
}

function handleStageWheel(event) {
  if (!(event.ctrlKey || event.metaKey)) return;
  event.preventDefault();
  const rect = els.workspaceStage.getBoundingClientRect();
  const localX = event.clientX - rect.left;
  const localY = event.clientY - rect.top;
  const worldX = (els.workspaceStage.scrollLeft + localX) / state.zoom;
  const worldY = (els.workspaceStage.scrollTop + localY) / state.zoom;
  const delta = event.deltaY < 0 ? 0.1 : -0.1;
  const nextZoom = clamp(state.zoom + delta, 0.3, 2);
  if (nextZoom === state.zoom) return;
  state.zoom = nextZoom;
  render();
  els.workspaceStage.scrollLeft = worldX * state.zoom - localX;
  els.workspaceStage.scrollTop = worldY * state.zoom - localY;
  persist();
}

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  pushHistory();
}

function initHistory() {
  historyStack = [snapshotState()];
  redoStack = [];
}

function snapshotState() {
  return JSON.stringify(state);
}

function pushHistory() {
  if (isApplyingHistory) return;
  const snapshot = snapshotState();
  if (historyStack[historyStack.length - 1] === snapshot) return;
  historyStack.push(snapshot);
  if (historyStack.length > 120) historyStack.shift();
  redoStack = [];
}

function undoHistory() {
  if (historyStack.length <= 1) return;
  const current = historyStack.pop();
  redoStack.push(current);
  applyHistorySnapshot(historyStack[historyStack.length - 1]);
}

function redoHistory() {
  if (!redoStack.length) return;
  const snapshot = redoStack.pop();
  historyStack.push(snapshot);
  applyHistorySnapshot(snapshot);
}

function applyHistorySnapshot(snapshot) {
  try {
    isApplyingHistory = true;
    state = hydrateStateFromParsed(JSON.parse(snapshot));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    render();
  } catch (error) {
  } finally {
    isApplyingHistory = false;
  }
}

function hydrateStateFromParsed(parsed) {
  const clean = defaultState();
  clean.page = { ...clean.page, ...(parsed.page || {}) };
  clean.zoom = clamp(Number(parsed.zoom) || 1, 0.3, 2);
  clean.elements = Array.isArray(parsed.elements)
    ? parsed.elements.map((item) => ({ ...createElement(item.type || 'rect'), ...item, parentId: item.parentId || null }))
    : [];
  clean.guides = {
    vertical: Array.isArray(parsed.guides?.vertical) ? parsed.guides.vertical : [],
    horizontal: Array.isArray(parsed.guides?.horizontal) ? parsed.guides.horizontal : []
  };
  clean.selectedIds = Array.isArray(parsed.selectedIds) ? parsed.selectedIds : (parsed.selectedId ? [parsed.selectedId] : []);
  clean.selectedGuide = parsed.selectedGuide || null;
  return clean;
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultState();
    return hydrateStateFromParsed(JSON.parse(raw));
  } catch (error) {
    return defaultState();
  }
}

function getSingleSelected() {
  if (state.selectedIds.length !== 1) return null;
  return getElementById(state.selectedIds[0]) || null;
}

function getSelectedFrameId() {
  const selected = getSingleSelected();
  return selected?.type === 'frame' ? selected.id : null;
}

function getElementById(id) {
  return state.elements.find((item) => item.id === id) || null;
}

function getChildren(parentId) {
  return state.elements.filter((item) => (item.parentId || null) === (parentId || null));
}

function getAbsolutePosition(element) {
  if (!element) return { x: 0, y: 0 };
  let x = element.x;
  let y = element.y;
  let parent = getElementById(element.parentId);
  while (parent) {
    x += parent.x;
    y += parent.y;
    parent = getElementById(parent.parentId);
  }
  return { x, y };
}

function getAbsoluteBounds(element) {
  const abs = getAbsolutePosition(element);
  return { x: abs.x, y: abs.y, w: element.w, h: element.h };
}

function getGroupBounds(ids) {
  const bounds = ids
    .map((id) => getElementById(id))
    .filter(Boolean)
    .map((element) => getAbsoluteBounds(element));
  if (!bounds.length) return { x: 0, y: 0, w: 0, h: 0 };
  const x = Math.min(...bounds.map((item) => item.x));
  const y = Math.min(...bounds.map((item) => item.y));
  const right = Math.max(...bounds.map((item) => item.x + item.w));
  const bottom = Math.max(...bounds.map((item) => item.y + item.h));
  return { x, y, w: right - x, h: bottom - y };
}

function setAbsolutePosition(element, absX, absY) {
  const parent = getElementById(element.parentId);
  const parentAbs = parent ? getAbsolutePosition(parent) : { x: 0, y: 0 };
  const maxW = parent ? parent.w : state.page.width;
  const maxH = parent ? parent.h : state.page.height;
  element.x = clamp(Math.round(absX - parentAbs.x), 0, Math.max(0, maxW - element.w));
  element.y = clamp(Math.round(absY - parentAbs.y), 0, Math.max(0, maxH - element.h));
}

function getDragSnap(rawDx, rawDy, ids, groupBounds) {
  let nextX = groupBounds.x + rawDx;
  let nextY = groupBounds.y + rawDy;
  if (state.page.snap) {
    nextX = snapValue(nextX);
    nextY = snapValue(nextY);
  }
  let dx = nextX - groupBounds.x;
  let dy = nextY - groupBounds.y;

  const xSnap = findBestSnap(
    [groupBounds.x + dx, groupBounds.x + dx + groupBounds.w / 2, groupBounds.x + dx + groupBounds.w],
    'x',
    ids
  );
  const ySnap = findBestSnap(
    [groupBounds.y + dy, groupBounds.y + dy + groupBounds.h / 2, groupBounds.y + dy + groupBounds.h],
    'y',
    ids
  );

  if (xSnap) dx += xSnap.delta;
  if (ySnap) dy += ySnap.delta;

  return {
    dx,
    dy,
    lines: {
      vertical: xSnap ? [xSnap.line] : [],
      horizontal: ySnap ? [ySnap.line] : []
    }
  };
}

function getResizeSnap(id, absX, absY, nextW, nextH, keepCircle) {
  let width = nextW;
  let height = nextH;
  const right = absX + nextW;
  const bottom = absY + nextH;
  const xSnap = findBestSnap([right], 'x', [id]);
  const ySnap = findBestSnap([bottom], 'y', [id]);

  if (xSnap) width += xSnap.delta;
  if (ySnap) height += ySnap.delta;

  if (keepCircle) {
    const size = Math.max(width, height);
    width = size;
    height = size;
  }

  return {
    w: Math.max(20, width),
    h: Math.max(20, height),
    lines: {
      vertical: xSnap ? [xSnap.line] : [],
      horizontal: ySnap ? [ySnap.line] : []
    }
  };
}

function findBestSnap(points, axis, excludeIds) {
  const candidates = collectSnapCandidates(axis, excludeIds);
  const threshold = 8 / state.zoom;
  let best = null;
  points.forEach((point) => {
    candidates.forEach((candidate) => {
      const delta = candidate - point;
      if (Math.abs(delta) > threshold) return;
      if (!best || Math.abs(delta) < Math.abs(best.delta)) {
        best = { delta, line: candidate };
      }
    });
  });
  return best;
}

function collectSnapCandidates(axis, excludeIds) {
  const exclude = new Set(excludeIds || []);
  const out = new Set();
  if (axis === 'x') {
    out.add(0);
    out.add(state.page.width / 2);
    out.add(state.page.width);
    state.guides.vertical.forEach((value) => out.add(value));
    state.elements.forEach((element) => {
      if (exclude.has(element.id)) return;
      const abs = getAbsoluteBounds(element);
      out.add(abs.x);
      out.add(abs.x + abs.w / 2);
      out.add(abs.x + abs.w);
    });
  } else {
    out.add(0);
    out.add(state.page.height / 2);
    out.add(state.page.height);
    state.guides.horizontal.forEach((value) => out.add(value));
    state.elements.forEach((element) => {
      if (exclude.has(element.id)) return;
      const abs = getAbsoluteBounds(element);
      out.add(abs.y);
      out.add(abs.y + abs.h / 2);
      out.add(abs.y + abs.h);
    });
  }
  return [...out];
}

function normalizeColor(color) {
  if (!color) return '#000000';
  if (/^#[0-9a-f]{6}$/i.test(color)) return color;
  if (/^#[0-9a-f]{3}$/i.test(color)) {
    return `#${color[1]}${color[1]}${color[2]}${color[2]}${color[3]}${color[3]}`;
  }
  return '#000000';
}


function hexToRgba(color, opacity = 1) {
  const hex = normalizeColor(color);
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${clamp(Number(opacity) || 0, 0, 1)})`;
}

function getFillCss(element) {
  if (element.fillMode === 'gradient') {
    const colorA = hexToRgba(element.gradientColorA || element.fill || '#000000', element.gradientOpacityA ?? 1);
    const colorB = hexToRgba(element.gradientColorB || element.stroke || '#000000', element.gradientOpacityB ?? 1);
    if ((element.gradientType || 'linear') === 'radial') {
      return `radial-gradient(circle at center, ${colorA} 0%, ${colorB} 100%)`;
    }
    return `linear-gradient(${Number(element.gradientAngle || 0)}deg, ${colorA} 0%, ${colorB} 100%)`;
  }
  return hexToRgba(element.fill || '#000000', element.fillOpacity ?? 1);
}

function applyElementVisualStyles(content, element) {
  content.style.borderStyle = 'solid';
  content.style.borderWidth = `${element.strokeWidth || 0}px`;
  content.style.borderColor = hexToRgba(element.stroke || '#000000', element.strokeOpacity ?? 1);
  content.style.borderRadius = `${element.radius || 0}px`;
  content.style.background = 'transparent';
  content.style.backgroundImage = 'none';
  content.style.color = '';
  content.style.webkitBackgroundClip = '';
  content.style.backgroundClip = '';
  if (element.type === 'text') {
    if (element.fillMode === 'gradient') {
      content.style.background = getFillCss(element);
      content.style.webkitBackgroundClip = 'text';
      content.style.backgroundClip = 'text';
      content.style.color = 'transparent';
    } else {
      content.style.color = hexToRgba(element.fill || '#000000', element.fillOpacity ?? 1);
    }
    return;
  }
  content.style.background = getFillCss(element);
}

function startInlineTextEdit(id) {
  const element = getElementById(id);
  if (!element || !['text', 'button'].includes(element.type)) return;
  const content = els.artboard.querySelector(`.canvas-element[data-id="${id}"] .element-content`);
  if (!content) return;
  state.selectedGuide = null;
  state.selectedIds = [id];
  content.contentEditable = 'true';
  content.spellcheck = false;
  content.classList.add('is-editing');
  content.focus();
  placeCaretAtEnd(content);

  let cancelEdit = false;

  const finishEdit = (save = true) => {
    content.removeEventListener('keydown', onKeydown);
    if (save) {
      const nextText = element.type === 'button'
        ? content.innerText.replace(/\n+/g, ' ').trim() || 'Clique aqui'
        : content.innerText.replace(/\r/g, '');
      element.text = nextText;
      persist();
    }
    content.contentEditable = 'false';
    content.classList.remove('is-editing');
    render();
  };

  const onKeydown = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      cancelEdit = true;
      content.blur();
      return;
    }
    if (element.type === 'button' && event.key === 'Enter') {
      event.preventDefault();
      content.blur();
    }
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      content.blur();
    }
  };

  content.addEventListener('blur', () => finishEdit(!cancelEdit), { once: true });
  content.addEventListener('keydown', onKeydown);
}

function placeCaretAtEnd(el) {
  const range = document.createRange();
  const sel = window.getSelection();
  range.selectNodeContents(el);
  range.collapse(false);
  sel.removeAllRanges();
  sel.addRange(range);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function snapValue(value) {
  if (!state.page.snap) return Math.round(value);
  const size = Math.max(2, Number(state.page.gridSize) || 16);
  return Math.round(value / size) * size;
}

function isSelected(id) {
  return state.selectedIds.includes(id);
}

function toggleSelection(id) {
  if (isSelected(id)) state.selectedIds = state.selectedIds.filter((item) => item !== id);
  else state.selectedIds = [...state.selectedIds, id];
}

function unique(arr) {
  return [...new Set(arr)];
}

function rectsIntersect(a, b) {
  return !(a.x + a.w < b.x || b.x + b.w < a.x || a.y + a.h < b.y || b.y + b.h < a.y);
}

function getSelectionRect(source) {
  const x = Math.min(source.startX, source.currentX);
  const y = Math.min(source.startY, source.currentY);
  const w = Math.abs(source.currentX - source.startX);
  const h = Math.abs(source.currentY - source.startY);
  return { x, y, w, h };
}

function toArtboardPoint(event) {
  const rect = els.artboard.getBoundingClientRect();
  return {
    x: clamp((event.clientX - rect.left) / state.zoom, 0, state.page.width),
    y: clamp((event.clientY - rect.top) / state.zoom, 0, state.page.height)
  };
}

function findTargetFrame(movingId, centerX, centerY) {
  const movingSet = new Set([movingId, ...getDescendantIds(movingId)]);
  const frames = state.elements.filter((item) => item.type === 'frame' && !movingSet.has(item.id));
  const matches = frames.filter((frame) => {
    const abs = getAbsoluteBounds(frame);
    return centerX >= abs.x && centerX <= abs.x + abs.w && centerY >= abs.y && centerY <= abs.y + abs.h;
  });
  matches.sort((a, b) => (a.w * a.h) - (b.w * b.h));
  return matches[0] || null;
}

function getDescendantIds(id) {
  let out = [];
  state.elements.filter((item) => item.parentId === id).forEach((child) => {
    out.push(child.id, ...getDescendantIds(child.id));
  });
  return out;
}

function isElementInSelectedTree(id, ids) {
  return ids.some((selectedId) => selectedId === id || getDescendantIds(selectedId).includes(id));
}

function downloadFile(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function importJsonFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const parsed = JSON.parse(String(reader.result || '{}'));
      state = defaultState();
      state.page = { ...state.page, ...(parsed.page || {}) };
      state.zoom = clamp(Number(parsed.zoom) || 1, 0.3, 2);
      state.elements = Array.isArray(parsed.elements)
        ? parsed.elements.map((item) => ({ ...createElement(item.type || 'rect'), ...item, parentId: item.parentId || null }))
        : [];
      state.guides = {
        vertical: Array.isArray(parsed.guides?.vertical) ? parsed.guides.vertical : [],
        horizontal: Array.isArray(parsed.guides?.horizontal) ? parsed.guides.horizontal : []
      };
      state.selectedIds = Array.isArray(parsed.selectedIds) ? parsed.selectedIds : (parsed.selectedId ? [parsed.selectedId] : []);
      state.selectedGuide = null;
      persist();
      render();
      alert('JSON importado com sucesso.');
    } catch (error) {
      alert('Não foi possível importar esse JSON.');
    }
  };
  reader.readAsText(file, 'utf-8');
}

function importImageFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    const imageElement = createElement('image', getSelectedFrameId(), {
      src: String(reader.result || ''),
      name: file.name.replace(/\.[^.]+$/, '') || 'Imagem'
    });
    state.elements.push(imageElement);
    state.selectedGuide = null;
    state.selectedIds = [imageElement.id];
    render();
    persist();
  };
  reader.readAsDataURL(file);
}

function exportHtml() {
  const html = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Exportado do editor visual V17</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#d5dae3;font-family:Arial,sans-serif}
.page{position:relative;width:${state.page.width}px;height:${state.page.height}px;margin:40px auto;background:${state.page.bg};overflow:hidden;box-shadow:0 24px 50px rgba(0,0,0,.18)}
.item{position:absolute;display:flex;align-items:center;justify-content:center;text-align:center;word-break:break-word;overflow:visible}
.item>.box{width:100%;height:100%;display:flex;align-items:center;justify-content:center;overflow:hidden;word-break:break-word}
.item.text>.box{display:block;text-align:left}
.item.image img{width:100%;height:100%;object-fit:cover;display:block}
.item.frame>.box{overflow:hidden;position:relative}
.frame-label{position:absolute;top:-22px;left:0;font-size:12px;background:rgba(44,102,203,.08);padding:4px 8px;border-radius:8px;color:#2c66cb;border:1px solid rgba(44,102,203,.2)}
.guide-v,.guide-h{position:absolute;background:rgba(76,141,255,.45)}
.guide-v{top:0;bottom:0;width:1px}.guide-h{left:0;right:0;height:1px}
</style>
</head>
<body>
<div class="page">${buildExportGuides()}${buildExportTree(null)}</div>
</body>
</html>`;
  downloadFile('pagina_exportada_v17.html', html, 'text/html');
}

function buildExportGuides() {
  const vertical = state.guides.vertical.map((value) => `<div class="guide-v" style="left:${value}px"></div>`).join('');
  const horizontal = state.guides.horizontal.map((value) => `<div class="guide-h" style="top:${value}px"></div>`).join('');
  return vertical + horizontal;
}

function buildExportTree(parentId) {
  return getChildren(parentId).map(buildExportNode).join('');
}

function buildExportNode(element) {
  const styles = [
    `left:${element.x}px`,
    `top:${element.y}px`,
    `width:${element.w}px`,
    `height:${element.h}px`,
    `opacity:${element.opacity ?? 1}`,
    `transform:rotate(${element.rotate || 0}deg)`
  ].join(';');

  const boxStyles = [
    element.type === 'text' ? 'background:transparent' : `background:${getFillCss(element)}`,
    `border:${element.strokeWidth || 0}px solid ${hexToRgba(element.stroke || '#000000', element.strokeOpacity ?? 1)}`,
    `border-radius:${element.radius || 0}px`,
    element.type === 'button' ? 'color:#ffffff' : '',
    element.type === 'text' ? buildExportTextStyle(element) : ''
  ].filter(Boolean).join(';');

  let inner = '';
  if (element.type === 'text' || element.type === 'button') {
    inner = escapeHtml(element.text || '');
  } else if (element.type === 'image') {
    inner = element.src ? `<img src="${element.src}" alt="${escapeHtml(element.name || 'Imagem')}">` : 'Imagem';
  }

  const typography = (element.type === 'text' || element.type === 'button')
    ? `font-size:${element.fontSize || 16}px;font-weight:${element.fontWeight || 400};`
    : '';

  const label = element.type === 'frame' ? `<div class="frame-label">${escapeHtml(element.name || 'Frame')}</div>` : '';
  const children = element.type === 'frame' ? buildExportTree(element.id) : '';

  return `<div class="item ${escapeHtml(element.type)}" style="${styles}">${label}<div class="box" style="${boxStyles};${typography}">${inner}${children}</div></div>`;
}

function buildExportTextStyle(element) {
  if (element.fillMode === 'gradient') {
    return `background:${getFillCss(element)};-webkit-background-clip:text;background-clip:text;color:transparent;`;
  }
  return `color:${hexToRgba(element.fill || '#000000', element.fillOpacity ?? 1)};`;
}

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
