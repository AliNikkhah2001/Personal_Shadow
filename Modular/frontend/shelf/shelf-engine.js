// Uses globals: THREE
// Also uses: ShelfMotion, ShelfCover, ShelfStripe, ShelfFoil, ShelfConfig

// ---- Minimal RoundedBoxGeometry (inline fallback) ----
class RoundedBoxGeometry extends THREE.BufferGeometry {
  constructor(width = 1, height = 1, depth = 1, radius = 0, radiusSegments = 1) {
    super();
    this.type = 'RoundedBoxGeometry';
    const box = new THREE.BoxGeometry(width, height, depth, radiusSegments, radiusSegments, radiusSegments);
    this.copy(box);
    box.dispose();
  }
}

// ---- Minimal OrbitControls (inline) ----
class OrbitControls {
  constructor(object, domElement) {
    this.object = object;
    this.domElement = domElement;
    this.enabled = true;
    this.enableDamping = true;
    this.dampingFactor = 0.075;
    this.enablePan = true;
    this.screenSpacePanning = true;
    this.enableZoom = true;
    this.minDistance = 2.7;
    this.maxDistance = 7.2;
    this.minPolarAngle = Math.PI * 0.22;
    this.maxPolarAngle = Math.PI * 0.78;
    this._target = new THREE.Vector3();
    this._spherical = new THREE.Spherical();
    this._sphericalDelta = new THREE.Spherical();
    this._scale = 1;
    this._panOffset = new THREE.Vector3();
    this._rotateStart = new THREE.Vector2();
    this._rotateEnd = new THREE.Vector2();
    this._rotateDelta = new THREE.Vector2();
    this._panStart = new THREE.Vector2();
    this._panEnd = new THREE.Vector2();
    this._panDelta = new THREE.Vector2();
    this._dollyStart = new THREE.Vector2();
    this._dollyEnd = new THREE.Vector2();
    this._dollyDelta = new THREE.Vector2();
    this._state = -1;
    this._STATE = { NONE: -1, ROTATE: 0, DOLLY: 1, PAN: 2, TOUCH_ROTATE: 3, TOUCH_PAN: 4, TOUCH_DOLLY_PAN: 5 };
    const scope = this;
    function getAutoRotationAngle() { return 2 * Math.PI / 60 / 60; }
    function getZoomScale() { return Math.pow(0.95, scope._scale); }
    function rotateLeft(angle) { scope._sphericalDelta.theta -= angle; }
    function rotateUp(angle) { scope._sphericalDelta.phi -= angle; }
    const panLeft = (function() { const v = new THREE.Vector3(); return function panLeft(distance, objectMatrix) { v.setFromMatrixColumn(objectMatrix, 0); v.multiplyScalar(-distance); scope._panOffset.add(v); }; })();
    const panUp = (function() { const v = new THREE.Vector3(); return function panUp(distance, objectMatrix) { v.setFromMatrixColumn(objectMatrix, 1); v.multiplyScalar(distance); scope._panOffset.add(v); }; })();
    const pan = (function() { const offset = new THREE.Vector3(); return function pan(deltaX, deltaY) { const element = scope.domElement; if (scope.object.isPerspectiveCamera) { const position = scope.object.position; offset.copy(position).sub(scope._target); let targetDistance = offset.length(); targetDistance *= Math.tan((scope.object.fov / 2) * Math.PI / 180.0); panLeft(2 * deltaX * targetDistance / element.clientHeight, scope.object.matrix); panUp(2 * deltaY * targetDistance / element.clientHeight, scope.object.matrix); } else { console.warn('WARNING: OrbitControls.js encountered an unknown camera type - pan disabled.'); scope.enablePan = false; } }; })();
    function dollyIn(dollyScale) { if (scope.object.isPerspectiveCamera) scope._scale /= dollyScale; else console.warn('WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled.'); }
    function dollyOut(dollyScale) { if (scope.object.isPerspectiveCamera) scope._scale *= dollyScale; else console.warn('WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled.'); }
    function handleMouseDownRotate(event) { scope._rotateStart.set(event.clientX, event.clientY); }
    function handleMouseDownDolly(event) { scope._dollyStart.set(event.clientX, event.clientY); }
    function handleMouseDownPan(event) { scope._panStart.set(event.clientX, event.clientY); }
    function handleMouseMoveRotate(event) { scope._rotateEnd.set(event.clientX, event.clientY); scope._rotateDelta.subVectors(scope._rotateEnd, scope._rotateStart).multiplyScalar(2 * Math.PI / scope.domElement.clientHeight); rotateLeft(scope._rotateDelta.x); rotateUp(scope._rotateDelta.y); scope._rotateStart.copy(scope._rotateEnd); scope.update(); }
    function handleMouseMoveDolly(event) { scope._dollyEnd.set(event.clientX, event.clientY); scope._dollyDelta.subVectors(scope._dollyEnd, scope._dollyStart); if (scope._dollyDelta.y > 0) dollyIn(getZoomScale()); else if (scope._dollyDelta.y < 0) dollyOut(getZoomScale()); scope._dollyStart.copy(scope._dollyEnd); scope.update(); }
    function handleMouseMovePan(event) { scope._panEnd.set(event.clientX, event.clientY); scope._panDelta.subVectors(scope._panEnd, scope._panStart).multiplyScalar(scope.object.isPerspectiveCamera ? 1 : 1); pan(scope._panDelta.x, scope._panDelta.y); scope._panStart.copy(scope._panEnd); scope.update(); }
    function handleMouseUp() {}
    function handleMouseWheel(event) { if (event.deltaY < 0) dollyOut(getZoomScale()); else if (event.deltaY > 0) dollyIn(getZoomScale()); scope.update(); }
    function handleKeyDown(event) {
      switch (event.code) {
        case scope.keys.UP: pan(0, scope.keyPanSpeed); scope.update(); break;
        case scope.keys.BOTTOM: pan(0, -scope.keyPanSpeed); scope.update(); break;
        case scope.keys.LEFT: pan(scope.keyPanSpeed, 0); scope.update(); break;
        case scope.keys.RIGHT: pan(-scope.keyPanSpeed, 0); scope.update(); break;
      }
    }
    function handleTouchStartRotate(event) { if (event.touches.length === 1) scope._rotateStart.set(event.touches[0].pageX, event.touches[0].pageY); else { const dx = event.touches[0].pageX - event.touches[1].pageX; const dy = event.touches[0].pageY - event.touches[1].pageY; const distance = Math.sqrt(dx * dx + dy * dy); scope._dollyStart.set(0, distance); scope._rotateStart.set(event.touches[0].pageX, event.touches[0].pageY); } }
    function handleTouchStartPan(event) { if (event.touches.length === 1) scope._panStart.set(event.touches[0].pageX, event.touches[0].pageY); }
    function handleTouchStartDollyPan(event) { if (event.touches.length === 2) { const dx = event.touches[0].pageX - event.touches[1].pageX; const dy = event.touches[0].pageY - event.touches[1].pageY; const distance = Math.sqrt(dx * dx + dy * dy); scope._dollyStart.set(0, distance); scope._panStart.set((event.touches[0].pageX + event.touches[1].pageX) / 2, (event.touches[0].pageY + event.touches[1].pageY) / 2); } }
    function handleTouchMoveRotate(event) { if (event.touches.length === 1) { scope._rotateEnd.set(event.touches[0].pageX, event.touches[0].pageY); scope._rotateDelta.subVectors(scope._rotateEnd, scope._rotateStart).multiplyScalar(2 * Math.PI / scope.domElement.clientHeight); rotateLeft(scope._rotateDelta.x); rotateUp(scope._rotateDelta.y); scope._rotateStart.copy(scope._rotateEnd); scope.update(); } else { const dx = event.touches[0].pageX - event.touches[1].pageX; const dy = event.touches[0].pageY - event.touches[1].pageY; const distance = Math.sqrt(dx * dx + dy * dy); scope._dollyEnd.set(0, distance); scope._dollyDelta.set(0, Math.pow(scope._dollyEnd.y / scope._dollyStart.y, scope._scale)); if (scope._dollyDelta.y > 1) dollyIn(getZoomScale()); else if (scope._dollyDelta.y < 1) dollyOut(getZoomScale()); scope._dollyStart.copy(scope._dollyEnd); scope.update(); const cx = (event.touches[0].pageX + event.touches[1].pageX) / 2; const cy = (event.touches[0].pageY + event.touches[1].pageY) / 2; const px = (event.touches[0].pageX - event.touches[1].pageX) / 2; const py = (event.touches[0].pageY - event.touches[1].pageY) / 2; scope._panEnd.set(cx, cy); scope._panDelta.subVectors(scope._panEnd, scope._panStart).multiplyScalar(scope.object.isPerspectiveCamera ? 1 : 1); pan(scope._panDelta.x, scope._panDelta.y); scope._panStart.copy(scope._panEnd); scope.update(); } }
    function handleTouchMovePan(event) { if (event.touches.length === 1) { scope._panEnd.set(event.touches[0].pageX, event.touches[0].pageY); scope._panDelta.subVectors(scope._panEnd, scope._panStart).multiplyScalar(scope.object.isPerspectiveCamera ? 1 : 1); pan(scope._panDelta.x, scope._panDelta.y); scope._panStart.copy(scope._panEnd); scope.update(); } }
    function handleTouchEnd() {}
    function onMouseDown(event) { if (!scope.enabled) return; event.preventDefault(); switch (event.button) { case 0: scope._state = scope._STATE.ROTATE; handleMouseDownRotate(event); scope.domElement.addEventListener('mousemove', handleMouseMoveRotate); scope.domElement.addEventListener('mouseup', handleMouseUp); break; case 1: scope._state = scope._STATE.DOLLY; handleMouseDownDolly(event); scope.domElement.addEventListener('mousemove', handleMouseMoveDolly); scope.domElement.addEventListener('mouseup', handleMouseUp); break; case 2: scope._state = scope._STATE.PAN; handleMouseDownPan(event); scope.domElement.addEventListener('mousemove', handleMouseMovePan); scope.domElement.addEventListener('mouseup', handleMouseUp); break; } }
    function onMouseWheel(event) { if (!scope.enabled || !scope.enableZoom) return; event.preventDefault(); handleMouseWheel(event); }
    function onMouseMove(event) { if (!scope.enabled) return; event.preventDefault(); switch (scope._state) { case scope._STATE.ROTATE: handleMouseMoveRotate(event); break; case scope._STATE.DOLLY: handleMouseMoveDolly(event); break; case scope._STATE.PAN: handleMouseMovePan(event); break; } }
    function onMouseUp(event) { scope.domElement.removeEventListener('mousemove', handleMouseMoveRotate); scope.domElement.removeEventListener('mousemove', handleMouseMoveDolly); scope.domElement.removeEventListener('mousemove', handleMouseMovePan); scope.domElement.removeEventListener('mouseup', handleMouseUp); scope._state = scope._STATE.NONE; }
    function onTouchStart(event) { if (!scope.enabled) return; event.preventDefault(); switch (event.touches.length) { case 1: scope._state = scope._STATE.TOUCH_ROTATE; handleTouchStartRotate(event); break; case 2: scope._state = scope._STATE.TOUCH_DOLLY_PAN; handleTouchStartDollyPan(event); break; } }
    function onTouchMove(event) { if (!scope.enabled) return; event.preventDefault(); event.stopPropagation(); switch (event.touches.length) { case 1: handleTouchMoveRotate(event); break; case 2: handleTouchMoveRotate(event); break; } }
    function onTouchEnd(event) { if (!scope.enabled) return; scope._state = scope._STATE.NONE; }
    function onContextMenu(event) { if (!scope.enabled) return; event.preventDefault(); }
    scope.keys = { UP: 'ArrowUp', LEFT: 'ArrowLeft', RIGHT: 'ArrowRight', BOTTOM: 'ArrowDown' };
    scope.keyPanSpeed = 7.0;
    scope.domElement.addEventListener('contextmenu', onContextMenu);
    scope.domElement.addEventListener('mousedown', onMouseDown);
    scope.domElement.addEventListener('wheel', onMouseWheel, { passive: false });
    scope.domElement.addEventListener('touchstart', onTouchStart, { passive: false });
    scope.domElement.addEventListener('touchend', onTouchEnd);
    scope.domElement.addEventListener('touchmove', onTouchMove, { passive: false });
    scope.domElement.addEventListener('keydown', handleKeyDown);
    scope.update();
  }
  update() {
    const offset = new THREE.Vector3().copy(this.object.position).sub(this._target);
    this._spherical.setFromVector3(offset);
    if (this.enableDamping) { this._spherical.theta += this._sphericalDelta.theta; this._spherical.phi += this._sphericalDelta.phi; } else { this._spherical.theta = this._spherical.theta + this._sphericalDelta.theta; this._spherical.phi = this._spherical.phi + this._sphericalDelta.phi; }
    this._spherical.phi = Math.max(this.minPolarAngle, Math.min(this.maxPolarAngle, this._spherical.phi));
    this._spherical.makeSafe();
    this._spherical.radius *= this._scale;
    this._spherical.radius = Math.max(this.minDistance, Math.min(this.maxDistance, this._spherical.radius));
    this._target.add(this._panOffset);
    this.object.position.setFromSpherical(this._spherical).add(this._target);
    this.object.lookAt(this._target);
    if (this.enableDamping) { this._sphericalDelta.theta *= (1 - this.dampingFactor); this._sphericalDelta.phi *= (1 - this.dampingFactor); this._panOffset.multiplyScalar(1 - this.dampingFactor); } else { this._sphericalDelta.set(0, 0); this._panOffset.set(0, 0, 0); }
    this._scale = 1;
  }
  dispose() {
    this.domElement.removeEventListener('contextmenu', onContextMenu);
    this.domElement.removeEventListener('mousedown', onMouseDown);
    this.domElement.removeEventListener('wheel', onMouseWheel);
    this.domElement.removeEventListener('touchstart', onTouchStart);
    this.domElement.removeEventListener('touchend', onTouchEnd);
    this.domElement.removeEventListener('touchmove', onTouchMove);
    this.domElement.removeEventListener('keydown', handleKeyDown);
  }
  get target() { return this._target; }
  set target(v) { this._target.copy(v); }
}
// Attach to THREE namespace for compatibility
THREE.RoundedBoxGeometry = RoundedBoxGeometry;
THREE.OrbitControls = OrbitControls;

const siteConfig = window.ShelfConfig;
const shelfTop = 0.34;
const browseCamera = new THREE.Vector3(0, 1.42, 6.65);
const browseTarget = new THREE.Vector3(0, 1.28, 0.15);
const pageColor = new THREE.Color("#e9dfca");
const shelfColor = new THREE.Color("#5a4132");
const clamp = THREE.MathUtils.clamp;
const focusInDuration = 0.46;
const focusOutDuration = 0.34;
const desktopDetailWidthRatio = 0.41;
const compactDetailWidthRatio = 0.48;
const desktopDetailMaxWidth = 620;
const compactDetailMaxWidth = 570;
const desktopFocusX = -0.58;
const desktopFocusZ = 1.66;
const desktopFocusScale = 1.08;
const mobileFocusZ = 1.4;
const mobileFocusScale = 0.92;
const inspectionIdleLift = 0.014;
const inspectionIdlePitch = THREE.MathUtils.degToRad(0.28);
const inspectionIdleYaw = THREE.MathUtils.degToRad(0.48);
const inspectionIdleRoll = THREE.MathUtils.degToRad(0.22);

const stripeBookCoverFacingRotationY = -Math.PI / 2;

function damp(current, target, lambda, delta) {
  return THREE.MathUtils.damp(current, target, lambda, delta);
}

function easeOutCubic(value) {
  const t = 1 - clamp(value, 0, 1);
  return 1 - t * t * t;
}

function toTexture(
  canvas,
  renderer,
  anisotropy = 8,
) {
  const texture = new THREE.CanvasTexture(canvas);
  texture.encoding = THREE.sRGBEncoding;
  texture.anisotropy = Math.min(
    anisotropy,
    renderer.capabilities.getMaxAnisotropy(),
  );
  texture.generateMipmaps = true;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  return texture;
}

function createLivingMaterial(color) {
  return new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: {
      uTime: { value: 0 },
      uStrength: { value: 0 },
      uColor: { value: new THREE.Color(color) },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      varying vec2 vUv;
      uniform float uTime;
      uniform float uStrength;
      uniform vec3 uColor;

      void main() {
        float diagonal = fract(vUv.x * 0.72 + vUv.y * 0.31 + uTime * 0.045);
        float sheen = smoothstep(0.44, 0.5, diagonal) * (1.0 - smoothstep(0.5, 0.57, diagonal));
        float edge = smoothstep(0.0, 0.18, vUv.x) * smoothstep(1.0, 0.82, vUv.x);
        float alpha = sheen * edge * uStrength * 0.32;
        gl_FragColor = vec4(uColor, alpha);
      }
    `,
  });
}

class ShelfEngine {
  canvas;
  booksData;
  callbacks;
  renderer;
  scene = new THREE.Scene();
  camera;
  controls;
  shelfGroup = new THREE.Group();
  shelfFurniture = new THREE.Group();
  runtimeBooks = [];
  pickTargets = [];
  raycaster = new THREE.Raycaster();
  pointer = new THREE.Vector2(10, 10);
  animationFrame = 0;
  resizeObserver;
  mode = "browse";
  selectedIndex = null;
  activeIndex = 0;
  presentedIndex = 0;
  pendingFocusIndex = null;
  browseMotionPhase = "idle";
  browseMotionProgress = 0;
  motionBookIndex = null;
  motionLayout = ShelfMotion.createMotionLayout([]);
  collisionRejects = 0;
  lastCollisionPair = null;
  scrollIndex = 0;
  targetScrollIndex = 0;
  focusProgress = 0;
  lastInputTime = 0;
  pointerDown = false;
  pointerId = null;
  pointerStartX = 0;
  pointerLastX = 0;
  pointerTravel = 0;
  reducedMotion = false;
  assetCount = 0;
  assetFailures = 0;
  stripeTextureCache = new Map();
  stripeTextures = new Set();
  stripeGeometry = null;
  stripeGeometrySize = new THREE.Vector3();
  focusCameraPosition = new THREE.Vector3();
  focusCameraTarget = new THREE.Vector3();
  responsiveBrowseCamera = browseCamera.clone();
  lastTimestamp = 0;
  lastDiagnosticsAt = 0;
  isDisposed = false;

  constructor(
    canvas,
    books,
    callbacks,
  ) {
    this.canvas = canvas;
    this.booksData = books;
    this.callbacks = callbacks;
    this.reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      powerPreference: "high-performance",
    });
    this.renderer.outputEncoding = THREE.sRGBEncoding;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.03;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;

    this.camera = new THREE.PerspectiveCamera(27, 1, 0.08, 80);
    this.camera.position.copy(browseCamera);
    this.camera.lookAt(browseTarget);

    this.controls = new THREE.OrbitControls(this.camera, this.canvas);
    this.controls.enabled = false;
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.075;
    this.controls.enablePan = true;
    this.controls.screenSpacePanning = true;
    this.controls.enableZoom = true;
    this.controls.minDistance = 2.7;
    this.controls.maxDistance = 7.2;
    this.controls.minPolarAngle = Math.PI * 0.22;
    this.controls.maxPolarAngle = Math.PI * 0.78;

    this.resizeObserver = new ResizeObserver(this.handleResize);
    this.setupScene();
    this.createBooks();
    this.bindEvents();
    this.resizeObserver.observe(canvas);
    this.handleResize();
    this.callbacks.onReady();
    this.callbacks.onStatus(`${this.booksData.length} volumes ready`);
    this.animate();
    if (siteConfig.enableOptionalStripeArchive) {
      void this.loadStripeAssets();
    }

    window.__PRESS_LIBRARY__ = {
      diagnostics: () => this.getDiagnostics(),
      focus: (index) => this.focusBook(index),
      browse: (index) => this.browseTo(index),
      returnToShelf: () => this.returnToShelf(),
    };
  }

  setupScene() {
    this.scene.background = new THREE.Color("#eee8db");
    this.scene.fog = new THREE.Fog("#eee8db", 10, 26);

    const hemisphere = new THREE.HemisphereLight("#fff8ea", "#6e5848", 2.4);
    this.scene.add(hemisphere);

    const key = new THREE.DirectionalLight("#fff6e7", 4.6);
    key.position.set(-4.2, 7.4, 5.5);
    key.castShadow = true;
    key.shadow.mapSize.set(
      window.innerWidth < 700 ? 1024 : 2048,
      window.innerWidth < 700 ? 1024 : 2048,
    );
    key.shadow.camera.left = -8;
    key.shadow.camera.right = 8;
    key.shadow.camera.top = 6;
    key.shadow.camera.bottom = -2;
    key.shadow.camera.near = 0.5;
    key.shadow.camera.far = 22;
    key.shadow.bias = -0.0005;
    this.scene.add(key);

    const rim = new THREE.DirectionalLight("#c8d5e5", 2.1);
    rim.position.set(5, 3, -4);
    this.scene.add(rim);

    const warmBounce = new THREE.PointLight("#d79b72", 1.2, 10, 2);
    warmBounce.position.set(-3, 0.4, 3.2);
    this.scene.add(warmBounce);

    const wall = new THREE.Mesh(
      new THREE.PlaneGeometry(34, 18),
      new THREE.MeshStandardMaterial({
        color: "#eee8db",
        roughness: 1,
        metalness: 0,
      }),
    );
    wall.position.set(0, 5, -3.2);
    wall.receiveShadow = true;
    this.scene.add(wall);

    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(36, 18),
      new THREE.MeshStandardMaterial({
        color: "#e7dfd0",
        roughness: 0.94,
        metalness: 0,
      }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.24;
    ground.receiveShadow = true;
    this.scene.add(ground);

    this.scene.add(this.shelfGroup);
    this.shelfGroup.add(this.shelfFurniture);
  }

  createBooks() {
    let cursor = 0;
    const gap = 0.045;

    this.booksData.forEach((book, index) => {
      cursor += book.thickness * 0.5;
      const runtime = this.createBook(book, index, cursor);
      this.runtimeBooks.push(runtime);
      this.shelfGroup.add(runtime.slot);
      if (book.coverImage) {
        void this.loadCustomCover(runtime, book.coverImage);
      }
      cursor += book.thickness * 0.5 + gap;
    });

    this.motionLayout = ShelfMotion.createMotionLayout(
      this.runtimeBooks.map((book) => ({
        width: book.width,
        thickness: book.data.thickness,
      })),
    );
    this.runtimeBooks.forEach((book, index) => {
      this.commitBookPose(
        book,
        index === 0
          ? ShelfMotion.presentedBookPose(this.motionLayout)
          : ShelfMotion.shelvedBookPose(this.motionLayout),
        false,
      );
    });

    const shelfWidth = cursor + 8;
    const shelfGeometry = new THREE.RoundedBoxGeometry(shelfWidth, 0.22, 1.72, 4, 0.045);
    const shelfMaterial = new THREE.MeshStandardMaterial({
      color: shelfColor,
      roughness: 0.62,
      metalness: 0.03,
    });
    const shelf = new THREE.Mesh(shelfGeometry, shelfMaterial);
    shelf.name = "continuousShelf";
    shelf.position.set(cursor * 0.5, shelfTop - 0.14, 0);
    shelf.castShadow = true;
    shelf.receiveShadow = true;
    this.shelfFurniture.add(shelf);

    const shelfEdge = new THREE.Mesh(
      new THREE.RoundedBoxGeometry(shelfWidth, 0.12, 0.16, 3, 0.025),
      new THREE.MeshPhysicalMaterial({
        color: "#4b3429",
        roughness: 0.46,
        clearcoat: 0.14,
        clearcoatRoughness: 0.5,
      }),
    );
    shelfEdge.position.set(cursor * 0.5, shelfTop - 0.08, 0.85);
    shelfEdge.castShadow = true;
    this.shelfFurniture.add(shelfEdge);
  }

  createBook(book, index, x) {
    const width = 1.31 + ((index % 5) - 2) * 0.018;
    const depth = book.thickness;
    const slot = new THREE.Group();
    slot.name = `bookSlot:${book.id}`;
    slot.position.set(x, shelfTop + book.height * 0.5, 0.04);

    const content = new THREE.Group();
    content.name = `bookPresentation:${book.id}`;
    slot.add(content);
    const pose = ShelfMotion.shelvedBookPose(this.motionLayout);
    content.position.set(pose.x, 0, pose.z);
    content.rotation.y = pose.yaw;
    content.scale.setScalar(pose.scale);

    const inspectionIdle = new THREE.Group();
    inspectionIdle.name = `bookInspectionIdle:${book.id}`;
    content.add(inspectionIdle);

    const physical = new THREE.Group();
    physical.name = `proceduralBook:${book.id}`;
    inspectionIdle.add(physical);

    const assetHolder = new THREE.Group();
    assetHolder.name = `stripePressBook:${book.id}`;
    inspectionIdle.add(assetHolder);

    const boardMaterial = new THREE.MeshPhysicalMaterial({
      color: book.cover,
      roughness: 0.78,
      metalness: 0,
      sheen: 0.36,
      sheenColor: new THREE.Color(book.ink),
      sheenRoughness: 0.82,
      clearcoat: book.motif === "gather" ? 0.12 : 0.03,
      clearcoatRoughness: 0.7,
    });
    const paperMaterial = new THREE.MeshStandardMaterial({
      color: pageColor,
      roughness: 0.88,
      metalness: 0,
    });

    const pageBlock = new THREE.Mesh(
      new THREE.RoundedBoxGeometry(
        width - 0.075,
        book.height - 0.105,
        Math.max(0.08, depth - 0.052),
        3,
        0.018,
      ),
      paperMaterial,
    );
    pageBlock.name = "pageBlock";
    pageBlock.castShadow = true;
    pageBlock.receiveShadow = true;
    physical.add(pageBlock);

    const boardGeometry = new THREE.RoundedBoxGeometry(
      width,
      book.height,
      0.034,
      4,
      0.025,
    );
    const frontBoard = new THREE.Mesh(boardGeometry, boardMaterial);
    frontBoard.name = "frontBoard";
    frontBoard.position.z = depth * 0.5;
    frontBoard.castShadow = true;
    frontBoard.receiveShadow = true;
    physical.add(frontBoard);

    const backBoard = new THREE.Mesh(boardGeometry, boardMaterial);
    backBoard.name = "backBoard";
    backBoard.position.z = -depth * 0.5;
    backBoard.castShadow = true;
    backBoard.receiveShadow = true;
    physical.add(backBoard);

    const spine = new THREE.Mesh(
      new THREE.RoundedBoxGeometry(0.055, book.height - 0.01, depth + 0.012, 3, 0.018),
      boardMaterial,
    );
    spine.name = "spine";
    spine.position.x = -width * 0.5 + 0.022;
    spine.castShadow = true;
    physical.add(spine);

    const headbandMaterial = new THREE.MeshPhysicalMaterial({
      color: book.accent,
      roughness: 0.62,
      metalness: 0.2,
    });
    const headbandGeometry = new THREE.CylinderGeometry(0.017, 0.017, width - 0.1, 10);
    headbandGeometry.rotateZ(Math.PI / 2);
    const headbandTop = new THREE.Mesh(headbandGeometry, headbandMaterial);
    headbandTop.position.set(0, book.height * 0.5 - 0.045, 0);
    physical.add(headbandTop);
    const headbandBottom = headbandTop.clone();
    headbandBottom.position.y = -book.height * 0.5 + 0.045;
    physical.add(headbandBottom);

    const frontTexture = toTexture(ShelfCover.createFrontCover(book), this.renderer);
    const titleTexture = toTexture(ShelfCover.createTitleDecal(book), this.renderer);
    const spineTexture = toTexture(ShelfCover.createSpineCover(book), this.renderer, 4);
    const backTexture = toTexture(ShelfCover.createBackCover(book), this.renderer);
    const textures = [frontTexture, titleTexture, spineTexture, backTexture];

    const frontSurface = new THREE.Mesh(
      new THREE.PlaneGeometry(width - 0.065, book.height - 0.065),
      new THREE.MeshPhysicalMaterial({
        map: frontTexture,
        roughness: 0.66,
        metalness: 0.02,
        clearcoat: book.motif === "gather" ? 0.18 : 0.05,
        clearcoatRoughness: 0.48,
      }),
    );
    frontSurface.name = "frontArtwork";
    frontSurface.position.z = depth * 0.5 + 0.019;
    physical.add(frontSurface);

    const titleDecal = new THREE.Mesh(
      new THREE.PlaneGeometry(width - 0.065, book.height - 0.065),
      new THREE.MeshBasicMaterial({
        map: titleTexture,
        transparent: true,
        alphaTest: 0.02,
        depthWrite: false,
        polygonOffset: true,
        polygonOffsetFactor: -2,
      }),
    );
    titleDecal.name = "accurateTitleDecal";
    titleDecal.position.z = depth * 0.5 + 0.026;
    titleDecal.visible = false;
    inspectionIdle.add(titleDecal);

    const backSurface = new THREE.Mesh(
      new THREE.PlaneGeometry(width - 0.065, book.height - 0.065),
      new THREE.MeshStandardMaterial({
        map: backTexture,
        roughness: 0.72,
      }),
    );
    backSurface.name = "backArtwork";
    backSurface.position.z = -depth * 0.5 - 0.019;
    backSurface.rotation.y = Math.PI;
    physical.add(backSurface);

    const spineSurface = new THREE.Mesh(
      new THREE.PlaneGeometry(depth - 0.02, book.height - 0.04),
      new THREE.MeshPhysicalMaterial({
        map: spineTexture,
        roughness: 0.68,
        metalness: 0.015,
      }),
    );
    spineSurface.name = "spineArtwork";
    spineSurface.rotation.y = -Math.PI / 2;
    spineSurface.position.x = -width * 0.5 - 0.019;
    physical.add(spineSurface);

    let livingMaterial;
    if (book.living) {
      livingMaterial = createLivingMaterial(book.accent);
      const shimmer = new THREE.Mesh(
        new THREE.PlaneGeometry(width - 0.07, book.height - 0.07),
        livingMaterial,
      );
      shimmer.name = "livingCoverShimmer";
      shimmer.position.z = depth * 0.5 + 0.034;
      inspectionIdle.add(shimmer);
    }

    const pickProxy = new THREE.Mesh(
      new THREE.BoxGeometry(width, book.height, depth + 0.07),
      new THREE.MeshBasicMaterial({
        transparent: true,
        opacity: 0,
        depthWrite: false,
      }),
    );
    pickProxy.name = `pick:${book.id}`;
    pickProxy.userData.bookIndex = index;
    inspectionIdle.add(pickProxy);
    this.pickTargets.push(pickProxy);

    return {
      data: book,
      index,
      slot,
      content,
      inspectionIdle,
      physical,
      assetHolder,
      frontSurface,
      titleDecal,
      pickProxy,
      livingMaterial,
      x,
      width,
      pose,
      hover: 0,
      targetHover: 0,
      idleAmount: 0,
      textures,
    };
  }

  bindEvents() {
    this.canvas.addEventListener("wheel", this.handleWheel, { passive: false });
    this.canvas.addEventListener("pointerdown", this.handlePointerDown);
    this.canvas.addEventListener("pointermove", this.handlePointerMove);
    this.canvas.addEventListener("pointerup", this.handlePointerUp);
    this.canvas.addEventListener("pointercancel", this.handlePointerCancel);
    this.canvas.addEventListener("pointerleave", this.handlePointerLeave);
    this.canvas.addEventListener("keydown", this.handleKeyDown);
    window.addEventListener("blur", this.handleWindowBlur);
  }

  handleWheel = (event) => {
    if (this.mode !== "browse") return;
    event.preventDefault();
    this.pendingFocusIndex = null;
    const dominant =
      Math.abs(event.deltaX) > Math.abs(event.deltaY)
        ? event.deltaX
        : event.deltaY;
    this.targetScrollIndex = clamp(
      this.targetScrollIndex + dominant * 0.0024,
      0,
      this.runtimeBooks.length - 1,
    );
    this.lastInputTime = performance.now();
  };

  handlePointerDown = (event) => {
    if (this.mode !== "browse") return;
    this.pointerDown = true;
    this.pointerId = event.pointerId;
    this.pointerStartX = event.clientX;
    this.pointerLastX = event.clientX;
    this.pointerTravel = 0;
    this.canvas.setPointerCapture(event.pointerId);
  };

  handlePointerMove = (event) => {
    this.updatePointer(event);
    if (this.mode !== "browse") return;

    if (this.pointerDown && event.pointerId === this.pointerId) {
      this.pendingFocusIndex = null;
      const delta = event.clientX - this.pointerLastX;
      this.pointerLastX = event.clientX;
      this.pointerTravel += Math.abs(delta);
      this.targetScrollIndex = clamp(
        this.targetScrollIndex - delta / Math.max(105, this.canvas.clientWidth * 0.11),
        0,
        this.runtimeBooks.length - 1,
      );
      this.lastInputTime = performance.now();
      this.canvas.classList.add("is-dragging");
      return;
    }

    this.updateHover();
  };

  handlePointerUp = (event) => {
    if (event.pointerId !== this.pointerId) return;
    const wasClick = this.pointerTravel < 7 && Math.abs(event.clientX - this.pointerStartX) < 7;
    this.pointerDown = false;
    this.pointerId = null;
    this.canvas.classList.remove("is-dragging");
    if (this.canvas.hasPointerCapture(event.pointerId)) {
      this.canvas.releasePointerCapture(event.pointerId);
    }
    if (this.mode === "browse" && wasClick) {
      this.updatePointer(event);
      const hit = this.raycastBook();
      if (hit !== null) this.focusBook(hit);
    }
  };

  handlePointerCancel = (event) => {
    if (event.pointerId !== this.pointerId) return;
    this.pointerDown = false;
    this.pointerId = null;
    this.canvas.classList.remove("is-dragging");
  };

  handlePointerLeave = () => {
    if (!this.pointerDown) {
      this.runtimeBooks.forEach((book) => {
        book.targetHover = 0;
      });
      this.canvas.style.cursor = "grab";
    }
  };

  handleWindowBlur = () => {
    this.pointerDown = false;
    this.pointerId = null;
    this.canvas.classList.remove("is-dragging");
  };

  handleKeyDown = (event) => {
    if (event.key === "Escape") {
      this.returnToShelf();
      return;
    }
    if ((event.key === "r" || event.key === "R") && this.mode === "inspect") {
      this.resetFocusView();
      return;
    }
    if (this.mode !== "browse") return;

    if (event.key === "ArrowRight") {
      event.preventDefault();
      this.browseBy(1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      this.browseBy(-1);
    } else if (event.key === "Home") {
      event.preventDefault();
      this.browseTo(0);
    } else if (event.key === "End") {
      event.preventDefault();
      this.browseTo(this.runtimeBooks.length - 1);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      this.focusBook(this.activeIndex);
    }
  };

  updatePointer(event) {
    const rect = this.canvas.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  }

  raycastBook() {
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hit = this.raycaster.intersectObjects(this.pickTargets, false)[0];
    return typeof hit?.object.userData.bookIndex === "number"
      ? hit.object.userData.bookIndex
      : null;
  }

  updateHover() {
    const hit = this.raycastBook();
    this.runtimeBooks.forEach((book) => {
      book.targetHover = book.index === hit ? 1 : 0;
    });
    this.canvas.style.cursor = hit === null ? "grab" : "pointer";
  }

  xAtIndex(index) {
    const lower = Math.floor(index);
    const upper = Math.min(this.runtimeBooks.length - 1, Math.ceil(index));
    const fraction = index - lower;
    return THREE.MathUtils.lerp(
      this.runtimeBooks[lower]?.x ?? 0,
      this.runtimeBooks[upper]?.x ?? 0,
      fraction,
    );
  }

  footprintFor(
    book,
    pose = book.pose,
  ) {
    return {
      id: book.data.id,
      x: book.x + pose.x,
      z: book.slot.position.z + pose.z,
      yaw: pose.yaw,
      scale: pose.scale,
      width: book.width,
      thickness: book.data.thickness,
    };
  }

  collisionFor(book, pose) {
    const proposed = this.footprintFor(book, pose);
    return (
      this.runtimeBooks.find(
        (other) =>
          other !== book &&
          ShelfMotion.bookFootprintsOverlap(
            proposed,
            this.footprintFor(other),
            this.motionLayout.collisionMargin,
          ),
      ) ?? null
    );
  }

  commitBookPose(
    book,
    pose,
    guardCollision = true,
  ) {
    if (guardCollision) {
      const collidedWith = this.collisionFor(book, pose);
      if (collidedWith) {
        this.collisionRejects += 1;
        this.lastCollisionPair = [book.data.id, collidedWith.data.id];
        return false;
      }
    }

    book.pose = { ...pose };
    book.content.position.x = pose.x;
    book.content.position.z = pose.z;
    book.content.rotation.y = pose.yaw;
    book.content.scale.setScalar(pose.scale);
    return true;
  }

  beginFocus(index) {
    if (
      this.mode !== "browse" ||
      this.browseMotionPhase !== "idle" ||
      this.presentedIndex !== index
    ) {
      return;
    }
    this.pendingFocusIndex = null;
    this.selectedIndex = index;
    this.focusProgress = 0;
    this.mode = "focusing";
    this.runtimeBooks.forEach((book) => {
      book.targetHover = 0;
    });
    this.callbacks.onMode(this.mode, index);
    this.callbacks.onStatus(
      `Opening ${this.runtimeBooks[index].data.shortTitle}`,
    );
  }

  updateBrowseMotion(delta) {
    if (this.browseMotionPhase === "idle") {
      if (this.presentedIndex === this.activeIndex) {
        if (this.pendingFocusIndex === this.activeIndex) {
          this.beginFocus(this.activeIndex);
        }
        return;
      }

      this.motionBookIndex = this.presentedIndex;
      this.browseMotionPhase =
        this.motionBookIndex === null ? "extract-next" : "retreat-current";
      if (this.motionBookIndex === null) {
        this.motionBookIndex = this.activeIndex;
      }
      this.browseMotionProgress = 0;
    }

    const phase = this.browseMotionPhase;
    const motionIndex = this.motionBookIndex;
    if (motionIndex === null) return;
    const duration = this.reducedMotion
      ? Math.max(0.055, ShelfMotion.browsePhaseDuration[phase] * 0.45)
      : ShelfMotion.browsePhaseDuration[phase];
    const nextProgress = clamp(
      this.browseMotionProgress + delta / duration,
      0,
      1,
    );
    const movingBook = this.runtimeBooks[motionIndex];
    const proposedPose = ShelfMotion.browseMotionPose(
      phase,
      nextProgress,
      this.motionLayout,
    );
    if (!this.commitBookPose(movingBook, proposedPose)) return;

    this.browseMotionProgress = nextProgress;
    if (nextProgress < 1) return;

    this.browseMotionProgress = 0;
    switch (phase) {
      case "retreat-current":
        this.browseMotionPhase = "turn-current";
        break;
      case "turn-current":
        this.browseMotionPhase = "shelve-current";
        break;
      case "shelve-current":
        this.presentedIndex = null;
        this.motionBookIndex = this.activeIndex;
        this.browseMotionPhase = "extract-next";
        break;
      case "extract-next":
        this.browseMotionPhase = "turn-next";
        break;
      case "turn-next":
        this.browseMotionPhase = "settle-next";
        break;
      case "settle-next":
        this.presentedIndex = motionIndex;
        this.motionBookIndex = null;
        this.browseMotionPhase = "idle";
        if (this.pendingFocusIndex === this.presentedIndex) {
          this.beginFocus(this.presentedIndex);
        }
        break;
    }
  }

  animate = () => {
    if (this.isDisposed) return;
    this.animationFrame = requestAnimationFrame(this.animate);
    const timestamp = performance.now();
    const elapsed = timestamp / 1000;
    const delta = clamp((timestamp - this.lastTimestamp) / 1000 || 1 / 60, 0, 0.05);
    this.lastTimestamp = timestamp;

    this.updateState(delta, timestamp);
    this.updateBooks(delta, elapsed);

    if (this.controls.enabled) this.controls.update();
    this.renderer.render(this.scene, this.camera);
    if (timestamp - this.lastDiagnosticsAt > 500) {
      const diagnostics = this.getDiagnostics();
      this.canvas.dataset.drawCalls = String(diagnostics.drawCalls);
      this.canvas.dataset.triangles = String(diagnostics.triangles);
      this.canvas.dataset.geometries = String(diagnostics.geometries);
      this.canvas.dataset.textures = String(diagnostics.textures);
      this.canvas.dataset.stripeAssets = String(
        diagnostics.stripeAssetsLoaded,
      );
      this.canvas.dataset.pixelRatio = String(diagnostics.pixelRatio);
      this.canvas.dataset.motionPhase = diagnostics.motionPhase;
      this.canvas.dataset.collisionFree = String(
        diagnostics.currentCollision === null,
      );
      this.canvas.dataset.collisionRejects = String(
        diagnostics.collisionRejects,
      );
      this.lastDiagnosticsAt = timestamp;
    }
  };

  updateState(delta, timestamp) {
    if (this.mode === "browse") {
      if (!this.pointerDown && timestamp - this.lastInputTime > 150) {
        this.targetScrollIndex = damp(
          this.targetScrollIndex,
          Math.round(this.targetScrollIndex),
          this.reducedMotion ? 18 : 8.5,
          delta,
        );
      }
      this.scrollIndex = damp(
        this.scrollIndex,
        this.targetScrollIndex,
        this.reducedMotion ? 20 : 10,
        delta,
      );
      this.focusProgress = damp(this.focusProgress, 0, 10, delta);
      this.camera.position.lerp(
        this.responsiveBrowseCamera,
        1 - Math.exp(-(this.reducedMotion ? 18 : 7) * delta),
      );
      this.camera.lookAt(browseTarget);
    } else if (this.mode === "focusing") {
      this.focusProgress = clamp(
        this.focusProgress +
          delta / (this.reducedMotion ? 0.08 : focusInDuration),
        0,
        1,
      );
      this.updateFocusCamera(delta);
      if (this.focusProgress >= 1) {
        this.mode = "inspect";
        this.controls.enabled = true;
        this.controls.target.copy(this.focusCameraTarget);
        this.callbacks.onMode(this.mode, this.selectedIndex);
        if (this.selectedIndex !== null) {
          this.callbacks.onStatus(
            `Inspecting ${this.runtimeBooks[this.selectedIndex].data.shortTitle}`,
          );
        }
      }
    } else if (this.mode === "returning") {
      this.controls.enabled = false;
      this.focusProgress = clamp(
        this.focusProgress -
          delta / (this.reducedMotion ? 0.08 : focusOutDuration),
        0,
        1,
      );
      this.applyFocusViewOffset(easeOutCubic(this.focusProgress));
      this.camera.position.lerp(
        this.responsiveBrowseCamera,
        1 - Math.exp(-(this.reducedMotion ? 24 : 14) * delta),
      );
      this.camera.lookAt(browseTarget);
      if (this.focusProgress <= 0) {
        if (this.selectedIndex !== null) {
          this.commitBookPose(
            this.runtimeBooks[this.selectedIndex],
            ShelfMotion.presentedBookPose(this.motionLayout),
          );
          this.presentedIndex = this.selectedIndex;
        }
        this.selectedIndex = null;
        this.mode = "browse";
        this.callbacks.onMode(this.mode, null);
        this.callbacks.onStatus(`${this.booksData.length} volumes ready`);
        this.canvas.focus({ preventScroll: true });
      }
    }

    const nextActive = clamp(
      Math.round(this.scrollIndex),
      0,
      this.runtimeBooks.length - 1,
    );
    if (nextActive !== this.activeIndex) {
      this.activeIndex = nextActive;
      this.callbacks.onActiveIndex(this.activeIndex);
    }
    this.shelfGroup.position.x = -this.xAtIndex(this.scrollIndex);
    if (this.mode === "browse") {
      this.updateBrowseMotion(delta);
    }
  }

  updateBooks(delta, elapsed) {
    const motionFocus =
      this.mode === "returning"
        ? this.focusProgress
        : easeOutCubic(this.focusProgress);
    const isolated = this.selectedIndex !== null && motionFocus > 0.72;
    this.shelfFurniture.visible = !isolated;
    const focusX = window.innerWidth < 760 ? 0 : desktopFocusX;
    const focusZ =
      window.innerWidth < 760 ? mobileFocusZ : desktopFocusZ;
    const focusScale =
      window.innerWidth < 760 ? mobileFocusScale : desktopFocusScale;

    if (this.selectedIndex !== null) {
      const selected = this.runtimeBooks[this.selectedIndex];
      this.commitBookPose(
        selected,
        ShelfMotion.focusedBookPose(
          motionFocus,
          this.motionLayout,
          focusX,
          focusZ,
          focusScale,
        ),
      );
    }

    this.runtimeBooks.forEach((book) => {
      book.hover = damp(book.hover, book.targetHover, 12, delta);

      const isSelected = book.index === this.selectedIndex;
      book.content.visible = !isolated || isSelected;
      book.content.position.y = isSelected ? motionFocus * 0.04 : 0;

      const idleTarget =
        isSelected && this.mode === "inspect" && !this.reducedMotion ? 1 : 0;
      book.idleAmount = damp(book.idleAmount, idleTarget, 5, delta);
      const idleStrength = isSelected ? book.idleAmount : 0;
      const idlePhase = elapsed * 0.78 + book.index * 0.37;
      book.inspectionIdle.position.y =
        Math.sin(idlePhase) * inspectionIdleLift * idleStrength;
      book.inspectionIdle.rotation.set(
        Math.sin(idlePhase * 0.73 + 0.8) *
          inspectionIdlePitch *
          idleStrength,
        Math.sin(idlePhase * 0.61) * inspectionIdleYaw * idleStrength,
        Math.sin(idlePhase * 0.89 + 1.7) *
          inspectionIdleRoll *
          idleStrength,
      );

      if (book.livingMaterial) {
        book.livingMaterial.uniforms.uTime.value = elapsed;
        const livingStrength =
          this.reducedMotion
            ? 0
            : isSelected
              ? 0.24 + motionFocus * 0.55
              : book.index === this.presentedIndex
                ? 0.24 + book.hover * 0.08
                : book.hover * 0.04;
        book.livingMaterial.uniforms.uStrength.value = damp(
          book.livingMaterial.uniforms.uStrength.value,
          livingStrength,
          5,
          delta,
        );
      }
    });
  }

  updateFocusCamera(delta) {
    if (this.selectedIndex === null) return;
    const selected = this.runtimeBooks[this.selectedIndex];
    const worldPosition = new THREE.Vector3();
    selected.content.getWorldPosition(worldPosition);
    this.frameFocusedBook(worldPosition, easeOutCubic(this.focusProgress));
    this.camera.position.lerp(
      this.focusCameraPosition,
      1 - Math.exp(-(this.reducedMotion ? 28 : 13) * delta),
    );
    this.camera.lookAt(this.focusCameraTarget);
  }

  applyFocusViewOffset(progress) {
    const width = Math.max(1, this.canvas.clientWidth);
    const height = Math.max(1, this.canvas.clientHeight);
    const isMobile = width < 760;
    const detailWidth =
      width <= 1020
        ? Math.min(compactDetailMaxWidth, width * compactDetailWidthRatio)
        : Math.min(desktopDetailMaxWidth, width * desktopDetailWidthRatio);
    const focusDistance = isMobile ? 5.8 : 5.4;
    const verticalHalfSpan =
      Math.tan(THREE.MathUtils.degToRad(this.camera.fov * 0.5)) * focusDistance;
    const clampedProgress = clamp(progress, 0, 1);
    const horizontalOffset = isMobile
      ? 0
      : detailWidth * 0.5 * clampedProgress;
    const verticalOffset = isMobile
      ? (0.28 / verticalHalfSpan) * height * 0.5 * clampedProgress
      : 0;

    if (clampedProgress <= 0.001) {
      this.camera.clearViewOffset();
      return;
    }

    this.camera.setViewOffset(
      width,
      height,
      horizontalOffset,
      verticalOffset,
      width,
      height,
    );
  }

  frameFocusedBook(
    worldPosition,
    compositionProgress = 1,
  ) {
    const isMobile = this.canvas.clientWidth < 760;
    const focusDistance = isMobile ? 5.8 : 5.4;
    this.applyFocusViewOffset(compositionProgress);

    this.focusCameraTarget.copy(worldPosition);
    this.focusCameraPosition.set(
      worldPosition.x + (isMobile ? 0 : 0.58),
      worldPosition.y + 0.12,
      worldPosition.z + focusDistance,
    );
  }

  handleResize = () => {
    const width = Math.max(1, this.canvas.clientWidth);
    const height = Math.max(1, this.canvas.clientHeight);
    const dprCap = width < 760 ? 1.5 : 1.75;
    this.responsiveBrowseCamera.set(
      0,
      width < 760 ? 1.5 : browseCamera.y,
      width < 760 ? 8.3 : browseCamera.z,
    );
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, dprCap));
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.fov = width < 600 ? 33 : width < 920 ? 30 : 27;
    this.camera.updateProjectionMatrix();
    if (this.mode === "browse" && this.focusProgress < 0.01) {
      this.camera.clearViewOffset();
      this.camera.position.copy(this.responsiveBrowseCamera);
      this.camera.lookAt(browseTarget);
    } else if (this.mode === "inspect" && this.selectedIndex !== null) {
      const worldPosition = new THREE.Vector3();
      this.runtimeBooks[this.selectedIndex].content.getWorldPosition(
        worldPosition,
      );
      this.frameFocusedBook(worldPosition);
    }
  };

  async loadStripeAssets() {
    try {
      this.callbacks.onStatus("Finishing the shelf");
      const [booksResponse, objResponse] = await Promise.all([
        fetch(`${ShelfStripe.STRIPE_ASSET_ROOT}/books.json`),
        fetch(`${ShelfStripe.STRIPE_ASSET_ROOT}/mesh/stripe-press-book.obj`),
      ]);
      if (!booksResponse.ok || !objResponse.ok) {
        throw new Error("Stripe Press asset archive unavailable");
      }
      const bookAssets = await booksResponse.json();
      const parsed = new OBJLoader().parse(await objResponse.text());
      const sourceMesh = parsed.children.find(
        (child) => child instanceof THREE.Mesh,
      );
      if (!sourceMesh) throw new Error("Shared book mesh unavailable");

      const geometry = sourceMesh.geometry.clone();
      geometry.computeBoundingBox();
      if (!geometry.boundingBox) throw new Error("Shared book bounds unavailable");
      geometry.boundingBox.getSize(this.stripeGeometrySize);
      if (
        this.stripeGeometrySize.x <= 0 ||
        this.stripeGeometrySize.y <= 0 ||
        this.stripeGeometrySize.z <= 0
      ) {
        throw new Error("Shared book bounds are invalid");
      }
      const geometryCenter = geometry.boundingBox.getCenter(new THREE.Vector3());
      geometry.translate(
        -geometryCenter.x,
        -geometryCenter.y,
        -geometryCenter.z,
      );
      geometry.computeBoundingBox();
      this.stripeGeometry = geometry;
      await Promise.allSettled(
        bookAssets.map((bookAsset) => this.loadStripeBook(bookAsset)),
      );
      this.callbacks.onStatus(`${this.booksData.length} volumes ready`);
    } catch {
      this.callbacks.onStatus(`${this.booksData.length} volumes ready`);
    }
  }

  textureFor(
    reference,
    color = false,
  ) {
    if (!reference?.local_file) {
      return Promise.resolve(null);
    }
    const key = reference.local_file;
    const cached = this.stripeTextureCache.get(key);
    if (cached) return cached;

    const promise = new THREE.TextureLoader()
      .loadAsync(ShelfStripe.stripeAssetUrl(key))
      .then((texture) => {
        texture.name = key;
        texture.encoding = color ? THREE.sRGBEncoding : THREE.LinearEncoding;
        texture.anisotropy = Math.min(
          8,
          this.renderer.capabilities.getMaxAnisotropy(),
        );
        this.stripeTextures.add(texture);
        return texture;
      })
      .catch(() => null);
    this.stripeTextureCache.set(key, promise);
    return promise;
  }

  async loadCustomCover(runtime, coverImage) {
    try {
      const texture = await new THREE.TextureLoader().loadAsync(coverImage);
      if (this.isDisposed) {
        texture.dispose();
        return;
      }

      texture.name = `customCover:${runtime.data.id}`;
      texture.colorSpace = THREE.sRGBEncoding;
      texture.anisotropy = Math.min(
        8,
        this.renderer.capabilities.getMaxAnisotropy(),
      );

      const material = runtime.frontSurface.material;
      const proceduralTexture = material.map;
      material.map = texture;
      material.needsUpdate = true;
      runtime.textures.push(texture);

      if (proceduralTexture) {
        const index = runtime.textures.indexOf(proceduralTexture);
        if (index >= 0) runtime.textures.splice(index, 1);
        proceduralTexture.dispose();
      }
    } catch {
    }
  }

  async loadStripeBook(bookAsset) {
    const runtime = this.runtimeBooks.find(
      (book) => book.data.id === bookAsset.slug,
    );
    if (!runtime || !this.stripeGeometry) return;

    try {
      const [diffuse, bump, foil] = await Promise.all([
        this.textureFor(bookAsset.textures.diffuseMapCustom, true),
        this.textureFor(
          bookAsset.textures.bumpMapCustom ?? bookAsset.textures.bumpMapBase,
        ),
        this.textureFor(bookAsset.textures.foilMap),
      ]);
      if (!diffuse || this.isDisposed) {
        throw new Error(`Missing cover texture for ${bookAsset.slug}`);
      }

      const foilSettings = ShelfFoil.stripeFoilSettings(bookAsset.material);
      const material = new THREE.MeshPhysicalMaterial({
        name: `stripePressMaterial:${bookAsset.slug}`,
        map: diffuse,
        bumpMap: bump,
        bumpScale: Number(bookAsset.material.bumpScaleCustom ?? 0.035),
        metalnessMap: foil,
        metalness: foil ? 0.22 : 0.04,
        roughness: 0.68,
        clearcoat: 0.12,
        clearcoatRoughness: 0.55,
      });
      if (foil && foilSettings.enabled) {
        material.onBeforeCompile = (shader) => {
          shader.uniforms.stripeFoilMap = { value: foil };
          shader.uniforms.stripeFoilOpacity = {
            value: foilSettings.opacity,
          };
          shader.uniforms.stripeFoilDetail = {
            value: foilSettings.detail,
          };
          shader.fragmentShader = ShelfFoil.addStripeFoilBlend(
            shader.fragmentShader,
          );
        };
        material.customProgramCacheKey = () => "stripe-colored-foil-v1";
        material.userData.stripeFoil = {
          opacity: foilSettings.opacity,
          detail: foilSettings.detail,
        };
      }
      const mesh = new THREE.Mesh(this.stripeGeometry, material);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      const root = new THREE.Group();
      root.name = `stripePressEdition:${bookAsset.slug}`;
      root.add(mesh);
      root.rotation.y = stripeBookCoverFacingRotationY;

      const targetWidth = 1.31 + ((runtime.index % 5) - 2) * 0.018;
      root.scale.set(
        runtime.data.thickness / this.stripeGeometrySize.x,
        runtime.data.height / this.stripeGeometrySize.y,
        targetWidth / this.stripeGeometrySize.z,
      );
      root.updateMatrixWorld(true);
      root.userData.displaySize = {
        width: targetWidth,
        height: runtime.data.height,
        thickness: runtime.data.thickness,
      };
      root.userData.coverFacing = "+Z";

      runtime.assetHolder.add(root);
      runtime.physical.visible = false;
      runtime.titleDecal.visible = false;
      runtime.textures.forEach((texture) => texture.dispose());
      runtime.textures.length = 0;
      this.assetCount += 1;
    } catch {
      this.assetFailures += 1;
    }
  }

  browseBy(direction) {
    if (this.mode !== "browse") return;
    this.browseTo(Math.round(this.targetScrollIndex) + direction);
  }

  browseTo(index) {
    if (this.mode !== "browse") return;
    const next = clamp(Math.round(index), 0, this.runtimeBooks.length - 1);
    this.pendingFocusIndex = null;
    this.targetScrollIndex = next;
    this.lastInputTime = performance.now() - 1000;
  }

  focusBook(index = this.activeIndex) {
    if (this.mode !== "browse") return;
    const next = clamp(Math.round(index), 0, this.runtimeBooks.length - 1);
    this.targetScrollIndex = next;
    this.scrollIndex = next;
    this.activeIndex = next;
    this.pendingFocusIndex = next;
    this.callbacks.onActiveIndex(next);
    this.callbacks.onStatus(
      `Preparing ${this.runtimeBooks[next].data.shortTitle}`,
    );
    if (
      this.browseMotionPhase === "idle" &&
      this.presentedIndex === next
    ) {
      this.beginFocus(next);
    }
  }

  returnToShelf() {
    if (this.mode === "browse" && this.pendingFocusIndex !== null) {
      this.pendingFocusIndex = null;
      this.callbacks.onStatus("Opening cancelled");
      return;
    }
    if (this.mode === "browse" || this.mode === "returning") return;
    this.controls.enabled = false;
    this.mode = "returning";
    this.callbacks.onMode(this.mode, this.selectedIndex);
    this.callbacks.onStatus("Returning to the complete shelf");
  }

  resetFocusView() {
    if (this.mode !== "inspect" || this.selectedIndex === null) return;
    const selected = this.runtimeBooks[this.selectedIndex];
    const worldPosition = new THREE.Vector3();
    selected.content.getWorldPosition(worldPosition);
    this.frameFocusedBook(worldPosition);
    this.controls.target.copy(this.focusCameraTarget);
    this.camera.position.copy(this.focusCameraPosition);
    this.controls.update();
  }

  findAnyCollision() {
    for (let leftIndex = 0; leftIndex < this.runtimeBooks.length; leftIndex += 1) {
      const left = this.runtimeBooks[leftIndex];
      for (
        let rightIndex = leftIndex + 1;
        rightIndex < this.runtimeBooks.length;
        rightIndex += 1
      ) {
        const right = this.runtimeBooks[rightIndex];
        if (
          ShelfMotion.bookFootprintsOverlap(
            this.footprintFor(left),
            this.footprintFor(right),
            this.motionLayout.collisionMargin,
          )
        ) {
          return [left.data.id, right.data.id];
        }
      }
    }
    return null;
  }

  getDiagnostics() {
    const info = this.renderer.info;
    return {
      mode: this.mode,
      activeIndex: this.activeIndex,
      selectedIndex: this.selectedIndex,
      books: this.runtimeBooks.length,
      stripeAssetsLoaded: this.assetCount,
      stripeAssetFailures: this.assetFailures,
      drawCalls: info.render.calls,
      triangles: info.render.triangles,
      geometries: info.memory.geometries,
      textures: info.memory.textures,
      pixelRatio: this.renderer.getPixelRatio(),
      motionPhase: this.browseMotionPhase,
      collisionRejects: this.collisionRejects,
      lastCollisionPair: this.lastCollisionPair,
      currentCollision: this.findAnyCollision(),
      canvas: {
        width: this.canvas.width,
        height: this.canvas.height,
        clientWidth: this.canvas.clientWidth,
        clientHeight: this.canvas.clientHeight,
      },
    };
  }

  dispose() {
    this.isDisposed = true;
    cancelAnimationFrame(this.animationFrame);
    this.resizeObserver.disconnect();
    this.controls.dispose();
    this.canvas.removeEventListener("wheel", this.handleWheel);
    this.canvas.removeEventListener("pointerdown", this.handlePointerDown);
    this.canvas.removeEventListener("pointermove", this.handlePointerMove);
    this.canvas.removeEventListener("pointerup", this.handlePointerUp);
    this.canvas.removeEventListener("pointercancel", this.handlePointerCancel);
    this.canvas.removeEventListener("pointerleave", this.handlePointerLeave);
    this.canvas.removeEventListener("keydown", this.handleKeyDown);
    window.removeEventListener("blur", this.handleWindowBlur);

    this.scene.traverse((object) => {
      if (!(object instanceof THREE.Mesh)) return;
      object.geometry?.dispose();
      const materials = Array.isArray(object.material)
        ? object.material
        : [object.material];
      materials.forEach((material) => material?.dispose());
    });
    this.runtimeBooks.forEach((book) => {
      book.textures.forEach((texture) => texture.dispose());
    });
    this.stripeTextures.forEach((texture) => texture.dispose());
    this.stripeTextureCache.clear();
    this.stripeTextures.clear();
    this.stripeGeometry = null;
    this.stripeGeometrySize.set(0, 0, 0);
    this.renderer.dispose();
    delete window.__PRESS_LIBRARY__;
  }
}

window.ShelfEngine = ShelfEngine;
