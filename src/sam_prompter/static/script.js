if (element._samPrompterInitialized) return;
element._samPrompterInitialized = true;

(function () {
    "use strict";

    var container = element.querySelector(".sam-prompter-container");
    var dataScript = element.querySelector("script.prompt-data");
    var canvasWrapper = container.querySelector(".canvas-wrapper");
    var canvas = canvasWrapper.querySelector("canvas");
    var ctx = canvas.getContext("2d");
    var coordDisplay = container.querySelector(".coord-display");
    var objectTabsEl = container.querySelector(".object-tabs");
    var addObjectBtn = container.querySelector(".add-object-btn");
    var undoBtn = container.querySelector(".undo-btn");
    var clearBtn = container.querySelector(".clear-btn");
    var clearAllBtn = container.querySelector(".clear-all-btn");
    var maskToggleBtn = container.querySelector(".mask-toggle-btn");
    var helpBtn = container.querySelector(".help-btn");
    var helpOverlay = container.querySelector(".help-overlay");
    var helpCloseBtn = container.querySelector(".help-close-btn");
    var dropZone = container.querySelector(".drop-zone");
    var fileInput = container.querySelector(".file-input");
    var clearImageBtn = container.querySelector(".clear-image-btn");
    var settingsBar = container.querySelector(".settings-bar");
    var settingsBtn = container.querySelector(".settings-btn");
    var objColorSwatches = container.querySelector(".obj-color-swatches");
    var pointSizeSlider = container.querySelector(".point-size-slider");
    var pointSizeValue = container.querySelector(".point-size-value");
    var maskOpacitySlider = container.querySelector(".mask-opacity-slider");
    var maskOpacityValue = container.querySelector(".mask-opacity-value");
    var boxLineWidthSlider = container.querySelector(".box-line-width-slider");
    var boxLineWidthValue = container.querySelector(".box-line-width-value");
    var imageToggleBtn = container.querySelector(".image-toggle-btn");
    var moveBtn = container.querySelector(".move-btn");
    var maximizeBtn = container.querySelector(".maximize-btn");
    var cutoutBtn = container.querySelector(".cutout-btn");

    var isMac = /Mac|iPhone|iPad/.test(navigator.platform);
    var ALT_KEY_LABEL = isMac ? "⌥ Option" : "Alt";

    // Patch help overlay to show platform-appropriate modifier key
    helpOverlay.querySelectorAll("kbd").forEach(function (kbd) {
        if (kbd.textContent.indexOf("Alt") !== -1) {
            kbd.textContent = kbd.textContent.replace("Alt", ALT_KEY_LABEL);
        }
    });

    var DRAG_THRESHOLD = 5;
    var MIN_ZOOM = 1;
    var MAX_ZOOM = 20;
    var ZOOM_SENSITIVITY = 0.001;
    var COLOR_PALETTE = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
        "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F"
    ];
    var VIEW_COLORS = [
        "#00CC00", "#0066FF", "#FF0000", "#FFCC00",
        "#FF00FF", "#00CCCC", "#FF6600", "#9933FF",
        "#FFFFFF", "#000000", "#FF69B4", "#00FF80"
    ];
    var maxObjects = parseInt(container.getAttribute("data-max-objects"), 10) || 8;
    var pointRadius = parseInt(container.getAttribute("data-point-radius"), 10) || 6;
    var maskAlpha = parseFloat(container.getAttribute("data-mask-alpha")) || 0.4;
    var boxLineWidth = 2;

    var _renderFrameId = null;
    function requestRender() {
        if (_renderFrameId) return;
        _renderFrameId = requestAnimationFrame(function () {
            _renderFrameId = null;
            renderAll();
        });
    }

    // Deferred processing-flag reset: waits until the next animation
    // frame so that Gradio's Svelte re-evaluation, mask decoding, and
    // canvas rendering are all complete before accepting new clicks.
    var _processingResetFrameId = null;
    function scheduleProcessingReset() {
        if (_processingResetFrameId) cancelAnimationFrame(_processingResetFrameId);
        _processingResetFrameId = requestAnimationFrame(function () {
            _processingResetFrameId = null;
            if (state.isProcessing) {
                state.isProcessing = false;
                updateCanvasCursor();
            }
        });
    }

    // Initialize sliders
    pointSizeSlider.value = pointRadius;
    pointSizeValue.textContent = pointRadius;
    maskOpacitySlider.value = Math.round(maskAlpha * 100);
    maskOpacityValue.textContent = Math.round(maskAlpha * 100) + "%";
    boxLineWidthSlider.value = boxLineWidth;
    boxLineWidthValue.textContent = boxLineWidth + "px";

    var state = {
        image: null,
        imageUrl: null,
        naturalWidth: 0,
        naturalHeight: 0,
        objects: [createEmptyObject(0)],
        activeObjectIndex: 0,
        masks: [],
        maskCanvases: [],
        showMasks: true,
        isDrawingBox: false,
        boxStartX: 0,
        boxStartY: 0,
        boxCurrentX: 0,
        boxCurrentY: 0,
        mouseDownX: 0,
        mouseDownY: 0,
        mouseDownButton: -1,
        didDrag: false,
        isPanning: false,
        panStartX: 0,
        panStartY: 0,
        panStartPanX: 0,
        panStartPanY: 0,
        zoom: 1,
        panX: 0,
        panY: 0,
        moveMode: false,
        spaceHeld: false,
        showImage: true,
        settingsVisible: true,
        rawMasks: [],
        // Upload state
        objectUrl: null,
        filePath: null,
        pendingEmit: false,
        imageSource: null,  // "upload" or "python"
        altHoverPointIndex: -1,
        altHoverBoxIndex: -1,
        maximized: false,
        cutoutMode: false,
        isProcessing: false
    };

    container.__samPrompterState = state;

    // Pre-computed 16x16 checkerboard tile (8px squares, white + light gray)
    var _checkerTile = (function () {
        var tile = document.createElement("canvas");
        tile.width = 16;
        tile.height = 16;
        var tCtx = tile.getContext("2d");
        tCtx.fillStyle = "#ffffff";
        tCtx.fillRect(0, 0, 16, 16);
        tCtx.fillStyle = "#cccccc";
        tCtx.fillRect(8, 0, 8, 8);
        tCtx.fillRect(0, 8, 8, 8);
        return tile;
    })();

    // Lazily-allocated offscreen canvas for cutout compositing
    var _cutoutCanvas = null;
    var _cutoutCtx = null;
    function getCutoutCanvas(w, h) {
        if (!_cutoutCanvas || _cutoutCanvas.width !== w || _cutoutCanvas.height !== h) {
            _cutoutCanvas = document.createElement("canvas");
            _cutoutCanvas.width = w;
            _cutoutCanvas.height = h;
            _cutoutCtx = _cutoutCanvas.getContext("2d");
        }
        return { canvas: _cutoutCanvas, ctx: _cutoutCtx };
    }

    function createEmptyObject(index) {
        return {
            points: [],
            labels: [],
            boxes: [],
            color: VIEW_COLORS[index % VIEW_COLORS.length],
            history: [],
            visible: true
        };
    }

    // --- Color swatches ---

    function renderColorSwatches() {
        // Object color swatches
        var activeColor = state.objects[state.activeObjectIndex].color;
        objColorSwatches.innerHTML = "";
        for (var i = 0; i < VIEW_COLORS.length; i++) {
            (function (color) {
                var btn = document.createElement("button");
                btn.className = "color-swatch" + (color === activeColor ? " active" : "");
                btn.style.background = color;
                btn.style.borderColor = color === activeColor ? color : "transparent";
                btn.title = color;
                btn.addEventListener("click", function () {
                    state.objects[state.activeObjectIndex].color = color;
                    redecodeMask(state.activeObjectIndex);
                    renderToolbar();
                    requestRender();
                });
                objColorSwatches.appendChild(btn);
            })(VIEW_COLORS[i]);
        }

    }

    function redecodeMask(index) {
        if (index < state.rawMasks.length && state.rawMasks[index]) {
            var raw = state.rawMasks[index];
            var color = (index < state.objects.length) ? state.objects[index].color : raw.color;
            state.maskCanvases[index] = decodeMask(raw.rle, color, 1.0);
        }
    }

    // --- Coordinate transforms ---

    function getCanvasDisplayRect() {
        var rect = canvas.getBoundingClientRect();
        return rect;
    }

    function clientToNatural(clientX, clientY) {
        var rect = getCanvasDisplayRect();
        var displayX = clientX - rect.left;
        var displayY = clientY - rect.top;
        var scaleDisplay = canvas.width / rect.width;
        var canvasX = displayX * scaleDisplay;
        var canvasY = displayY * scaleDisplay;
        var natX = (canvasX - state.panX) / state.zoom;
        var natY = (canvasY - state.panY) / state.zoom;
        return { x: natX, y: natY };
    }

    function naturalToCanvas(natX, natY) {
        return {
            x: natX * state.zoom + state.panX,
            y: natY * state.zoom + state.panY
        };
    }

    function isInImageBounds(natX, natY) {
        return natX >= 0 && natX <= state.naturalWidth && natY >= 0 && natY <= state.naturalHeight;
    }

    // Ratio of canvas internal pixels to CSS display pixels.
    // Multiplying a screen-pixel size by this factor gives the
    // equivalent size in canvas (= natural image) coordinates.
    function getDisplayScale() {
        var rect = getCanvasDisplayRect();
        if (!rect.width) return 1;
        return canvas.width / rect.width;
    }

    // --- Zoom/Pan helpers ---

    function clampPan() {
        if (state.zoom <= 1) {
            state.panX = 0;
            state.panY = 0;
            return;
        }
        var maxPanX = 0;
        var minPanX = canvas.width - canvas.width * state.zoom;
        var maxPanY = 0;
        var minPanY = canvas.height - canvas.height * state.zoom;
        if (state.panX > maxPanX) state.panX = maxPanX;
        if (state.panX < minPanX) state.panX = minPanX;
        if (state.panY > maxPanY) state.panY = maxPanY;
        if (state.panY < minPanY) state.panY = minPanY;
    }

    function zoomToCenter(newZoom) {
        newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, newZoom));
        var cx = canvas.width / 2;
        var cy = canvas.height / 2;
        state.panX = cx - (cx - state.panX) * (newZoom / state.zoom);
        state.panY = cy - (cy - state.panY) * (newZoom / state.zoom);
        state.zoom = newZoom;
        clampPan();
        requestRender();
    }

    function resetZoom() {
        state.zoom = 1;
        state.panX = 0;
        state.panY = 0;
        requestRender();
    }

    function toggleMaximize() {
        state.maximized = !state.maximized;
        container.classList.toggle("maximized", state.maximized);
        document.body.style.overflow = state.maximized ? "hidden" : "";
        if (state.image) {
            requestAnimationFrame(function () {
                resizeCanvas();
                resetZoom();
            });
        }
    }

    function isMoveModeActive() {
        return state.moveMode || state.spaceHeld;
    }

    function updateCanvasCursor() {
        container.classList.toggle("is-processing", state.isProcessing);
        if (state.isProcessing) return;
        if (isMoveModeActive()) {
            canvas.style.cursor = state.isPanning ? "grabbing" : (state.zoom > 1 ? "grab" : "default");
        } else {
            canvas.style.cursor = "crosshair";
        }
    }

    // --- RLE mask decode ---

    function decodeMask(rle, color, alpha) {
        var h = rle.size[0], w = rle.size[1];
        var offscreen = document.createElement("canvas");
        offscreen.width = w;
        offscreen.height = h;
        var offCtx = offscreen.getContext("2d");
        var imgData = offCtx.createImageData(w, h);
        var d = imgData.data;
        var r, g, b;
        if (Array.isArray(color)) {
            r = color[0]; g = color[1]; b = color[2];
        } else {
            r = parseInt(color.slice(1, 3), 16);
            g = parseInt(color.slice(3, 5), 16);
            b = parseInt(color.slice(5, 7), 16);
        }
        var a = Math.round((alpha !== undefined ? alpha : maskAlpha) * 255);
        var pos = 0;
        for (var i = 0; i < rle.counts.length; i++) {
            var c = rle.counts[i];
            if (i % 2 === 1) {
                for (var j = pos; j < pos + c; j++) {
                    var row = j % h;
                    var col = (j / h) | 0;
                    var idx = (row * w + col) * 4;
                    d[idx] = r;
                    d[idx + 1] = g;
                    d[idx + 2] = b;
                    d[idx + 3] = a;
                }
            }
            pos += c;
        }
        offCtx.putImageData(imgData, 0, 0);
        return offscreen;
    }

    // --- Canvas sizing ---

    function resizeCanvas() {
        if (!state.image) return;
        var wrapperWidth = canvasWrapper.clientWidth;
        var aspect = state.naturalWidth / state.naturalHeight;
        var displayWidth = wrapperWidth;
        var displayHeight = displayWidth / aspect;

        // In maximized mode the wrapper has a fixed height (flex: 1).
        // Fit the canvas within both dimensions to prevent overflow.
        if (state.maximized) {
            var wrapperHeight = canvasWrapper.clientHeight;
            if (wrapperHeight > 0 && displayHeight > wrapperHeight) {
                displayHeight = wrapperHeight;
                displayWidth = displayHeight * aspect;
            }
        }

        // Only update internal dimensions when they actually changed;
        // setting canvas.width/height (even to the same value) clears
        // the pixel buffer which causes a visible flicker.
        if (canvas.width !== state.naturalWidth || canvas.height !== state.naturalHeight) {
            canvas.width = state.naturalWidth;
            canvas.height = state.naturalHeight;
        }
        canvas.style.width = displayWidth + "px";
        canvas.style.height = displayHeight + "px";
        canvasWrapper.style.minHeight = "";
    }

    // --- Visibility sync (survives Gradio template re-rendering) ---

    function syncVisibility() {
        if (state.image) {
            dropZone.classList.add("hidden");
        } else {
            dropZone.classList.remove("hidden");
        }
        // Restore settings bar visibility from state
        if (state.settingsVisible) {
            settingsBar.classList.remove("hidden");
            settingsBtn.classList.add("active");
        } else {
            settingsBar.classList.add("hidden");
            settingsBtn.classList.remove("active");
        }
        // Restore maximized state
        var wasMaximized = container.classList.contains("maximized");
        container.classList.toggle("maximized", state.maximized);
        document.body.style.overflow = state.maximized ? "hidden" : "";
        // After restoring the class the wrapper dimensions change;
        // schedule a resize so the canvas fits the new layout.
        if (state.maximized && !wasMaximized && state.image) {
            requestAnimationFrame(function () {
                resizeCanvas();
                requestRender();
            });
        }
    }

    // --- Rendering ---

    function renderAll() {
        syncVisibility();
        if (!state.image) return;

        var ds = getDisplayScale();

        // Clear in screen space
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Dark background visible when zoomed/panned
        if (state.zoom > 1) {
            ctx.fillStyle = "#1a1a1a";
            ctx.fillRect(0, 0, canvas.width, canvas.height);
        }

        // Apply zoom+pan transform
        ctx.save();
        ctx.setTransform(state.zoom, 0, 0, state.zoom, state.panX, state.panY);

        if (!state.cutoutMode) {
            // 1. Image (conditionally)
            if (state.showImage) {
                ctx.drawImage(state.image, 0, 0, state.naturalWidth, state.naturalHeight);
            } else {
                ctx.fillStyle = "#222222";
                ctx.fillRect(0, 0, state.naturalWidth, state.naturalHeight);
            }

            // 2. Masks (with dynamic opacity via globalAlpha)
            if (state.showMasks) {
                ctx.globalAlpha = maskAlpha;
                for (var m = 0; m < state.maskCanvases.length; m++) {
                    if (state.maskCanvases[m] && m < state.objects.length && state.objects[m].visible) {
                        ctx.drawImage(state.maskCanvases[m], 0, 0, state.naturalWidth, state.naturalHeight);
                    }
                }
                ctx.globalAlpha = 1.0;
            }
        } else {
            // Cutout mode: checkerboard + foreground pixels only where masks exist
            var checkerPattern = ctx.createPattern(_checkerTile, "repeat");
            ctx.fillStyle = checkerPattern;
            ctx.fillRect(0, 0, state.naturalWidth, state.naturalHeight);

            // Composite visible masks then clip the original image
            var co = getCutoutCanvas(state.naturalWidth, state.naturalHeight);
            co.ctx.clearRect(0, 0, state.naturalWidth, state.naturalHeight);

            // Union all visible mask canvases (source-over)
            co.ctx.globalCompositeOperation = "source-over";
            for (var cm = 0; cm < state.maskCanvases.length; cm++) {
                if (state.maskCanvases[cm] && cm < state.objects.length && state.objects[cm].visible) {
                    co.ctx.drawImage(state.maskCanvases[cm], 0, 0, state.naturalWidth, state.naturalHeight);
                }
            }

            // Keep image pixels only where mask alpha > 0
            co.ctx.globalCompositeOperation = "source-in";
            co.ctx.drawImage(state.image, 0, 0, state.naturalWidth, state.naturalHeight);
            co.ctx.globalCompositeOperation = "source-over";

            ctx.drawImage(co.canvas, 0, 0, state.naturalWidth, state.naturalHeight);
        }

        // 3. Prompts
        for (var oi = 0; oi < state.objects.length; oi++) {
            if (!state.objects[oi].visible) continue;
            drawObjectPrompts(state.objects[oi], oi === state.activeObjectIndex, ds);
        }

        // 4. Alt+hover delete indicator (point)
        if (state.altHoverPointIndex >= 0) {
            var aObj = state.objects[state.activeObjectIndex];
            if (aObj && state.altHoverPointIndex < aObj.points.length) {
                var apt = aObj.points[state.altHoverPointIndex];
                var hoverRadius = (pointRadius + 4) * ds / state.zoom;
                ctx.beginPath();
                ctx.arc(apt[0], apt[1], hoverRadius, 0, Math.PI * 2);
                ctx.strokeStyle = "#FF0000";
                ctx.lineWidth = 2 * ds / state.zoom;
                ctx.setLineDash([4 * ds / state.zoom, 3 * ds / state.zoom]);
                ctx.stroke();
                ctx.setLineDash([]);
            }
        }

        // 5. Alt+hover delete indicator (box)
        if (state.altHoverBoxIndex >= 0) {
            var bObj = state.objects[state.activeObjectIndex];
            if (bObj && state.altHoverBoxIndex < bObj.boxes.length) {
                var hBox = bObj.boxes[state.altHoverBoxIndex];
                ctx.strokeStyle = "#FF0000";
                ctx.lineWidth = 2 * ds / state.zoom;
                ctx.setLineDash([4 * ds / state.zoom, 3 * ds / state.zoom]);
                ctx.strokeRect(hBox[0], hBox[1], hBox[2] - hBox[0], hBox[3] - hBox[1]);
                ctx.setLineDash([]);
            }
        }

        ctx.restore();

        // 6. Rubber-band box (in canvas pixel space, not zoomed)
        if (state.isDrawingBox) {
            drawRubberBand(ds);
        }
    }

    function contrastStroke(hexColor) {
        var r = parseInt(hexColor.slice(1, 3), 16);
        var g = parseInt(hexColor.slice(3, 5), 16);
        var b = parseInt(hexColor.slice(5, 7), 16);
        // Perceived luminance
        var lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        return lum > 0.7 ? "#000000" : "#ffffff";
    }

    function drawObjectPrompts(obj, isActive, ds) {
        var color = obj.color;
        var stroke = contrastStroke(color);
        var baseRadius = pointRadius * ds / state.zoom;

        // Dim inactive objects so the active one stands out
        if (!isActive) {
            ctx.globalAlpha = 0.35;
        }

        // Draw boxes
        for (var b = 0; b < obj.boxes.length; b++) {
            var box = obj.boxes[b];
            ctx.strokeStyle = color;
            ctx.lineWidth = boxLineWidth * ds / state.zoom;
            ctx.setLineDash([6 * ds / state.zoom, 4 * ds / state.zoom]);
            ctx.strokeRect(box[0], box[1], box[2] - box[0], box[3] - box[1]);
            ctx.setLineDash([]);
        }

        // Draw points
        for (var p = 0; p < obj.points.length; p++) {
            var pt = obj.points[p];
            var label = obj.labels[p];
            var px = pt[0];
            var py = pt[1];

            if (label === 1) {
                // Foreground: colored circle with contrast outline
                ctx.beginPath();
                ctx.arc(px, py, baseRadius, 0, Math.PI * 2);
                ctx.fillStyle = color;
                ctx.fill();
                ctx.strokeStyle = stroke;
                ctx.lineWidth = 1.5 * ds / state.zoom;
                ctx.stroke();
            } else {
                // Background: object-colored circle with X mark
                ctx.beginPath();
                ctx.arc(px, py, baseRadius, 0, Math.PI * 2);
                ctx.fillStyle = color;
                ctx.fill();
                ctx.strokeStyle = stroke;
                ctx.lineWidth = 1.5 * ds / state.zoom;
                ctx.stroke();

                // X mark
                var xSize = baseRadius * 0.8;
                ctx.beginPath();
                ctx.moveTo(px - xSize, py - xSize);
                ctx.lineTo(px + xSize, py + xSize);
                ctx.moveTo(px + xSize, py - xSize);
                ctx.lineTo(px - xSize, py + xSize);
                ctx.strokeStyle = stroke;
                ctx.lineWidth = 2 * ds / state.zoom;
                ctx.stroke();
            }
        }

        // Restore full opacity after drawing inactive object
        if (!isActive) {
            ctx.globalAlpha = 1.0;
        }
    }

    function drawRubberBand(ds) {
        var p1 = naturalToCanvas(state.boxStartX, state.boxStartY);
        var p2 = naturalToCanvas(state.boxCurrentX, state.boxCurrentY);
        var color = state.objects[state.activeObjectIndex].color;
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = boxLineWidth * ds;
        ctx.setLineDash([6 * ds, 4 * ds]);
        // Parse hex to rgba for fill
        var r = parseInt(color.slice(1, 3), 16);
        var g = parseInt(color.slice(3, 5), 16);
        var b = parseInt(color.slice(5, 7), 16);
        ctx.fillStyle = "rgba(" + r + "," + g + "," + b + ",0.1)";
        var x = Math.min(p1.x, p2.x);
        var y = Math.min(p1.y, p2.y);
        var w = Math.abs(p2.x - p1.x);
        var h = Math.abs(p2.y - p1.y);
        ctx.fillRect(x, y, w, h);
        ctx.strokeRect(x, y, w, h);
        ctx.setLineDash([]);
        ctx.restore();
    }

    function renderToolbar() {
        var html = "";
        for (var i = 0; i < state.objects.length; i++) {
            var obj = state.objects[i];
            var activeClass = i === state.activeObjectIndex ? " active" : "";
            var hiddenClass = !obj.visible ? " hidden-object" : "";
            var promptCount = obj.points.length + obj.boxes.length;
            var tabStyle = activeClass ? ' style="border-left: 3px solid ' + obj.color + ';"' : "";
            html += '<button class="object-tab' + activeClass + hiddenClass + '"' + tabStyle + ' data-index="' + i + '">';
            html += '<span class="color-dot" style="background:' + obj.color + '"></span>';
            html += "Obj " + (i + 1);
            if (promptCount > 0) html += " (" + promptCount + ")";
            var eyeSvg = obj.visible
                ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>'
                : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';
            html += ' <span class="visibility-toggle" data-vis="' + i + '">' + eyeSvg + "</span>";
            if (state.objects.length > 1) {
                html += ' <span class="delete-tab" data-delete="' + i + '">&times;</span>';
            }
            html += "</button>";
        }
        objectTabsEl.innerHTML = html;

        // Bind tab clicks
        var tabs = objectTabsEl.querySelectorAll(".object-tab");
        for (var t = 0; t < tabs.length; t++) {
            (function (tab) {
                tab.addEventListener("click", function (e) {
                    if (e.target.classList.contains("delete-tab") || e.target.getAttribute("data-delete") !== null) {
                        return;
                    }
                    if (e.target.classList.contains("visibility-toggle") || e.target.getAttribute("data-vis") !== null) {
                        return;
                    }
                    var idx = parseInt(tab.getAttribute("data-index"), 10);
                    state.activeObjectIndex = idx;
                    renderToolbar();
                    requestRender();
                });
            })(tabs[t]);
        }

        // Bind visibility toggle clicks
        var visBtns = objectTabsEl.querySelectorAll(".visibility-toggle");
        for (var vi = 0; vi < visBtns.length; vi++) {
            (function (btn) {
                btn.addEventListener("click", function (e) {
                    e.stopPropagation();
                    var idx = parseInt(btn.getAttribute("data-vis"), 10);
                    state.objects[idx].visible = !state.objects[idx].visible;
                    renderToolbar();
                    requestRender();
                });
            })(visBtns[vi]);
        }

        // Bind delete clicks
        var deleteBtns = objectTabsEl.querySelectorAll(".delete-tab");
        for (var d = 0; d < deleteBtns.length; d++) {
            (function (btn) {
                btn.addEventListener("click", function (e) {
                    e.stopPropagation();
                    var idx = parseInt(btn.getAttribute("data-delete"), 10);
                    deleteObject(idx);
                });
            })(deleteBtns[d]);
        }

        // Update add button state
        addObjectBtn.disabled = state.objects.length >= maxObjects;

        // Update undo/clear button states
        var activeObj = state.objects[state.activeObjectIndex];
        undoBtn.disabled = !activeObj || activeObj.history.length === 0;
        clearBtn.disabled = !activeObj || (activeObj.points.length === 0 && activeObj.boxes.length === 0);

        var hasAnyPrompts = state.objects.some(function (o) {
            return o.points.length > 0 || o.boxes.length > 0;
        });
        clearAllBtn.disabled = !hasAnyPrompts;

        // Mask toggle
        if (state.showMasks) {
            maskToggleBtn.classList.add("active");
        } else {
            maskToggleBtn.classList.remove("active");
        }

        // Move mode
        if (isMoveModeActive()) {
            moveBtn.classList.add("active");
        } else {
            moveBtn.classList.remove("active");
        }

        // Clear image button
        clearImageBtn.disabled = !state.image;

        // Image toggle
        if (state.showImage) {
            imageToggleBtn.classList.add("active");
        } else {
            imageToggleBtn.classList.remove("active");
        }

        // Cutout mode
        if (state.cutoutMode) {
            cutoutBtn.classList.add("active");
        } else {
            cutoutBtn.classList.remove("active");
        }

        // Restore slider value labels (Svelte template re-evaluation clears textContent)
        pointSizeValue.textContent = pointRadius;
        maskOpacityValue.textContent = Math.round(maskAlpha * 100) + "%";
        boxLineWidthValue.textContent = boxLineWidth + "px";

        // Color swatches
        renderColorSwatches();
    }

    // --- Object management ---

    function addObject() {
        if (state.isProcessing) return;
        if (state.objects.length >= maxObjects) return;
        var newObj = createEmptyObject(state.objects.length);
        state.objects.push(newObj);
        state.activeObjectIndex = state.objects.length - 1;
        renderToolbar();
        requestRender();
    }

    function deleteObject(index) {
        if (state.isProcessing) return;
        if (state.objects.length <= 1) {
            clearActiveObject();
            return;
        }
        state.objects.splice(index, 1);
        if (state.activeObjectIndex >= state.objects.length) {
            state.activeObjectIndex = state.objects.length - 1;
        } else if (state.activeObjectIndex > index) {
            state.activeObjectIndex--;
        }
        // Reassign colors and re-decode affected masks
        for (var i = 0; i < state.objects.length; i++) {
            state.objects[i].color = VIEW_COLORS[i % VIEW_COLORS.length];
            redecodeMask(i);
        }
        renderToolbar();
        requestRender();
        emitPromptData();
    }

    function clearActiveObject() {
        if (state.isProcessing) return;
        var obj = state.objects[state.activeObjectIndex];
        if (obj.points.length === 0 && obj.boxes.length === 0) return;
        obj.history.push({
            type: "clear",
            points: obj.points.slice(),
            labels: obj.labels.slice(),
            boxes: obj.boxes.map(function (b) { return b.slice(); })
        });
        obj.points = [];
        obj.labels = [];
        obj.boxes = [];
        // Clear stale mask so it doesn't render with wrong color
        if (state.activeObjectIndex < state.maskCanvases.length) {
            state.maskCanvases[state.activeObjectIndex] = null;
        }
        if (state.activeObjectIndex < state.rawMasks.length) {
            state.rawMasks[state.activeObjectIndex] = null;
        }
        renderToolbar();
        requestRender();
        emitPromptData();
    }

    function clearAll() {
        if (state.isProcessing) return;
        state.objects = [createEmptyObject(0)];
        state.activeObjectIndex = 0;
        state.rawMasks = [];
        state.maskCanvases = [];
        renderToolbar();
        requestRender();
        emitPromptData();
    }

    // --- Prompt operations ---

    function addPoint(natX, natY, label) {
        if (state.isProcessing) return;
        var obj = state.objects[state.activeObjectIndex];
        obj.history.push({ type: "point" });
        obj.points.push([Math.round(natX), Math.round(natY)]);
        obj.labels.push(label);
        renderToolbar();
        requestRender();
        emitPromptData();
    }

    function addBox(x1, y1, x2, y2) {
        if (state.isProcessing) return;
        var bx1 = Math.round(Math.min(x1, x2));
        var by1 = Math.round(Math.min(y1, y2));
        var bx2 = Math.round(Math.max(x1, x2));
        var by2 = Math.round(Math.max(y1, y2));
        // Ignore tiny boxes
        if (Math.abs(bx2 - bx1) < 3 && Math.abs(by2 - by1) < 3) return;
        var obj = state.objects[state.activeObjectIndex];
        obj.history.push({ type: "box" });
        obj.boxes.push([bx1, by1, bx2, by2]);
        renderToolbar();
        requestRender();
        emitPromptData();
    }

    function undoLastPrompt() {
        if (state.isProcessing) return;
        var obj = state.objects[state.activeObjectIndex];
        if (obj.history.length === 0) return;
        var last = obj.history.pop();
        if (last.type === "point") {
            obj.points.pop();
            obj.labels.pop();
        } else if (last.type === "box") {
            obj.boxes.pop();
        } else if (last.type === "delete-point") {
            obj.points.splice(last.index, 0, last.point);
            obj.labels.splice(last.index, 0, last.label);
        } else if (last.type === "delete-box") {
            obj.boxes.splice(last.index, 0, last.box);
        } else if (last.type === "clear") {
            obj.points = last.points;
            obj.labels = last.labels;
            obj.boxes = last.boxes;
        }
        renderToolbar();
        requestRender();
        emitPromptData();
    }

    function findNearestPoint(natX, natY) {
        var obj = state.objects[state.activeObjectIndex];
        var ds = getDisplayScale();
        var hitRadius = pointRadius * 2 * ds / state.zoom;
        var bestDist = Infinity;
        var bestIdx = -1;
        for (var i = 0; i < obj.points.length; i++) {
            var dx = obj.points[i][0] - natX;
            var dy = obj.points[i][1] - natY;
            var dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < hitRadius && dist < bestDist) {
                bestDist = dist;
                bestIdx = i;
            }
        }
        return bestIdx;
    }

    function deletePointAt(index) {
        if (state.isProcessing) return;
        var obj = state.objects[state.activeObjectIndex];
        if (index < 0 || index >= obj.points.length) return;
        var point = obj.points[index].slice();
        var label = obj.labels[index];
        obj.history.push({ type: "delete-point", index: index, point: point, label: label });
        obj.points.splice(index, 1);
        obj.labels.splice(index, 1);
        renderToolbar();
        requestRender();
        emitPromptData();
    }

    function distToSegment(px, py, ax, ay, bx, by) {
        var dx = bx - ax, dy = by - ay;
        var lenSq = dx * dx + dy * dy;
        if (lenSq === 0) return Math.sqrt((px - ax) * (px - ax) + (py - ay) * (py - ay));
        var t = ((px - ax) * dx + (py - ay) * dy) / lenSq;
        t = Math.max(0, Math.min(1, t));
        var projX = ax + t * dx, projY = ay + t * dy;
        return Math.sqrt((px - projX) * (px - projX) + (py - projY) * (py - projY));
    }

    function findNearestBox(natX, natY) {
        var obj = state.objects[state.activeObjectIndex];
        var ds = getDisplayScale();
        var hitRadius = boxLineWidth * 3 * ds / state.zoom;
        var bestDist = Infinity;
        var bestIdx = -1;
        for (var i = 0; i < obj.boxes.length; i++) {
            var b = obj.boxes[i];
            var x1 = b[0], y1 = b[1], x2 = b[2], y2 = b[3];
            // Distance to each of the four edges
            var d = Math.min(
                distToSegment(natX, natY, x1, y1, x2, y1),  // top
                distToSegment(natX, natY, x2, y1, x2, y2),  // right
                distToSegment(natX, natY, x2, y2, x1, y2),  // bottom
                distToSegment(natX, natY, x1, y2, x1, y1)   // left
            );
            if (d < hitRadius && d < bestDist) {
                bestDist = d;
                bestIdx = i;
            }
        }
        return { index: bestIdx, dist: bestDist };
    }

    function deleteBoxAt(index) {
        if (state.isProcessing) return;
        var obj = state.objects[state.activeObjectIndex];
        if (index < 0 || index >= obj.boxes.length) return;
        var box = obj.boxes[index].slice();
        obj.history.push({ type: "delete-box", index: index, box: box });
        obj.boxes.splice(index, 1);
        renderToolbar();
        requestRender();
        emitPromptData();
    }

    // --- JS → Python communication ---

    function hasAnyPrompts() {
        return state.objects.some(function (obj) {
            return obj.points.length > 0 || obj.boxes.length > 0;
        });
    }

    function emitPromptData() {
        // Skip backend call when no object has actual prompts (points/boxes)
        if (!hasAnyPrompts()) return;
        // Defer if user uploaded a file but server path not yet available
        if (state.imageSource === "upload" && state.image && !state.filePath) {
            state.pendingEmit = true;
            return;
        }
        var prompts = state.objects.map(function (obj) {
            return {
                points: obj.points.slice(),
                labels: obj.labels.slice(),
                boxes: obj.boxes.map(function (b) { return b.slice(); })
            };
        });
        var payload = { prompts: prompts };
        if (state.imageSource === "upload" && state.filePath) {
            payload.imagePath = state.filePath;
            payload.imageSize = { width: state.naturalWidth, height: state.naturalHeight };
        }
        if (state.imageSource === "python" && state.imageUrl) {
            var prefix = "/gradio_api/file=";
            if (state.imageUrl.startsWith(prefix)) {
                payload.imagePath = state.imageUrl.slice(prefix.length);
            }
            payload.imageSize = { width: state.naturalWidth, height: state.naturalHeight };
        }
        props.value = JSON.stringify(payload);
        trigger("input");
        state.isProcessing = true;
        updateCanvasCursor();
    }

    // --- MutationObserver (Python → JS) ---

    function handleDataUpdate() {
        var raw = dataScript.textContent.trim();
        if (!raw || raw === "null") {
            // Only reset if image was from Python (not user upload)
            if (state.imageSource !== "upload") {
                state.image = null;
                state.imageUrl = null;
                state.rawMasks = [];
                state.maskCanvases = [];
            }
            // Restore dynamically-populated toolbar elements (swatches,
            // object tabs) that Gradio's Svelte template re-evaluation
            // clears when it resets ${value} after the Python handler
            // output is applied.
            scheduleProcessingReset();
            if (state.image) {
                resizeCanvas();
                renderToolbar();
            }
            requestRender();
            return;
        }

        var data;
        try {
            data = JSON.parse(raw);
        } catch (e) {
            return;
        }

        // Schedule deferred processing reset only for actual Python
        // responses (which contain "masks", "image", or "clearPrompts" keys).
        // The Svelte echo of props.value (which only has "prompts") must
        // NOT reset the flag, otherwise isProcessing would be cleared
        // immediately via microtask before Python even responds.
        if (state.isProcessing && ("masks" in data || "image" in data || "clearPrompts" in data)) {
            scheduleProcessingReset();
        }

        // Update maxObjects limit if Python specified it
        if (typeof data.maxObjects === "number" && data.maxObjects > 0) {
            maxObjects = data.maxObjects;
            container.setAttribute("data-max-objects", maxObjects);
            // Trim objects if exceeding new limit
            while (state.objects.length > maxObjects) {
                state.objects.pop();
            }
            if (state.activeObjectIndex >= state.objects.length) {
                state.activeObjectIndex = Math.max(0, state.objects.length - 1);
            }
        }

        // Python requested clearing all user-drawn prompts (points & boxes)
        if (data.clearPrompts) {
            state.objects = [createEmptyObject(0)];
            state.activeObjectIndex = 0;
            // If this is a clear-only payload (no image), just re-render
            if (!("image" in data)) {
                state.rawMasks = [];
                state.maskCanvases = [];
                if (state.image) {
                    resizeCanvas();
                }
                renderToolbar();
                requestRender();
                return;
            }
        }

        // Decode masks (store raw for re-decoding, decode at alpha=1.0 for globalAlpha control)
        if (data.masks && data.masks.length > 0) {
            var numMasks = data.masks.length;
            var numObjects = state.objects.length;

            // Initialize sparse arrays (one slot per object, null = no mask)
            var newRaw = [];
            var newCanvases = [];
            for (var si = 0; si < numObjects; si++) {
                newRaw.push(null);
                newCanvases.push(null);
            }

            if (numMasks >= numObjects) {
                // 1:1 (or more) mapping — direct index
                for (var di = 0; di < numObjects; di++) {
                    newRaw[di] = data.masks[di];
                    newCanvases[di] = decodeMask(data.masks[di].rle, state.objects[di].color, 1.0);
                }
            } else {
                // Fewer masks than objects — backend likely skipped empty
                // prompts.  Map returned masks to objects that have prompts.
                var promptedIndices = [];
                for (var pi = 0; pi < numObjects; pi++) {
                    var pObj = state.objects[pi];
                    if (pObj.points.length > 0 || pObj.boxes.length > 0) {
                        promptedIndices.push(pi);
                    }
                }

                if (numMasks === promptedIndices.length) {
                    // Perfect match — assign each mask to its prompted object
                    for (var mi = 0; mi < numMasks; mi++) {
                        var idx = promptedIndices[mi];
                        newRaw[idx] = data.masks[mi];
                        newCanvases[idx] = decodeMask(data.masks[mi].rle, state.objects[idx].color, 1.0);
                    }
                } else {
                    // Fallback: direct index mapping (original behaviour)
                    for (var fi = 0; fi < numMasks && fi < numObjects; fi++) {
                        newRaw[fi] = data.masks[fi];
                        newCanvases[fi] = decodeMask(data.masks[fi].rle, state.objects[fi].color, 1.0);
                    }
                }
            }

            state.rawMasks = newRaw;
            state.maskCanvases = newCanvases;
        } else if ("masks" in data) {
            // Python explicitly returned empty masks — clear.
            // Skip when the key is absent (JS echo in Svelte Phase 1).
            state.rawMasks = [];
            state.maskCanvases = [];
        }

        if (data.colors) {
            for (var ci = 0; ci < data.colors.length && ci < COLOR_PALETTE.length; ci++) {
                COLOR_PALETTE[ci] = data.colors[ci];
            }
        }

        // If the user uploaded an image, keep displaying it (blob URL)
        // and only update masks — do NOT reload from the Python cache URL.
        // Re-render the toolbar because Gradio's template re-evaluation
        // resets dynamically-populated DOM elements (swatches, object tabs).
        if (state.imageSource === "upload" && state.image) {
            resizeCanvas();
            renderToolbar();
            requestRender();
            return;
        }

        // Load image if URL changed (Python-provided image)
        if (data.image && data.image !== state.imageUrl) {
            // Detect mask-only updates for the same underlying image: lossy
            // re-encoding produces a different cache URL each time, so we
            // check whether the response is really just new masks rather
            // than a genuinely new image.
            var isMaskUpdate = state.imageSource === "python" &&
                state.image &&
                data.masks && data.masks.length > 0 &&
                (data.width || 0) === state.naturalWidth &&
                (data.height || 0) === state.naturalHeight;

            state.imageUrl = data.image;
            state.imageSource = "python";
            // Clean up previous blob URL if any
            if (state.objectUrl) {
                URL.revokeObjectURL(state.objectUrl);
                state.objectUrl = null;
            }
            state.filePath = null;
            var img = new Image();
            img.crossOrigin = "anonymous";
            img.onload = function () {
                state.image = img;
                state.naturalWidth = data.width || img.naturalWidth;
                state.naturalHeight = data.height || img.naturalHeight;
                if (!isMaskUpdate) {
                    state.objects = [createEmptyObject(0)];
                    state.activeObjectIndex = 0;
                    state.zoom = 1;
                    state.panX = 0;
                    state.panY = 0;
                }
                resizeCanvas();
                renderToolbar();
                requestRender();
            };
            img.src = data.image;
        } else if (data.image === state.imageUrl && state.image) {
            // Same image, just masks updated — re-render toolbar to restore
            // dynamically-populated elements after Gradio template re-evaluation.
            resizeCanvas();
            renderToolbar();
            requestRender();
        }
    }

    var observer = new MutationObserver(function () {
        handleDataUpdate();
    });
    observer.observe(dataScript, { childList: true, characterData: true, subtree: true });

    // Gradio may reset DOM attributes when re-rendering the template.
    // Re-apply drop-zone visibility if Gradio resets the class.
    var domObserver = new MutationObserver(function () {
        var shouldBeHidden = !!state.image;
        var isHidden = dropZone.classList.contains("hidden");
        if (shouldBeHidden !== isHidden) {
            syncVisibility();
        }
    });
    domObserver.observe(dropZone, { attributes: true, attributeFilter: ["class"] });

    // Similarly, restore settings-bar visibility if Gradio resets the class.
    var settingsObserver = new MutationObserver(function () {
        var shouldBeVisible = state.settingsVisible;
        var isHidden = settingsBar.classList.contains("hidden");
        if (shouldBeVisible === isHidden) {
            syncVisibility();
        }
    });
    settingsObserver.observe(settingsBar, { attributes: true, attributeFilter: ["class"] });

    // Restore maximized / is-processing classes if Gradio resets the
    // container's class attribute via its DOM-diffing algorithm.
    var containerObserver = new MutationObserver(function () {
        var shouldBeMaximized = state.maximized;
        var isMaximized = container.classList.contains("maximized");
        if (shouldBeMaximized !== isMaximized) {
            syncVisibility();
        }
        var shouldBeProcessing = state.isProcessing;
        var isProcessing = container.classList.contains("is-processing");
        if (shouldBeProcessing !== isProcessing) {
            container.classList.toggle("is-processing", shouldBeProcessing);
        }
    });
    containerObserver.observe(container, { attributes: true, attributeFilter: ["class"] });

    // --- Mouse events ---

    canvas.addEventListener("mousedown", function (e) {
        if (!state.image || state.isProcessing) return;

        // Middle button → always pan
        if (e.button === 1) {
            e.preventDefault();
            state.isPanning = true;
            state.didDrag = false;
            state.panStartX = e.clientX;
            state.panStartY = e.clientY;
            state.panStartPanX = state.panX;
            state.panStartPanY = state.panY;
            canvas.style.cursor = "grabbing";
            return;
        }

        // Left button in move mode → pan
        if (e.button === 0 && isMoveModeActive()) {
            state.isPanning = true;
            state.didDrag = false;
            state.panStartX = e.clientX;
            state.panStartY = e.clientY;
            state.panStartPanX = state.panX;
            state.panStartPanY = state.panY;
            if (state.zoom > 1) {
                canvas.style.cursor = "grabbing";
            }
            return;
        }

        // Normal mode: record mousedown for point/box
        state.mouseDownX = e.clientX;
        state.mouseDownY = e.clientY;
        state.mouseDownButton = e.button;
        state.didDrag = false;

        if (e.button === 0) {
            var nat = clientToNatural(e.clientX, e.clientY);
            if (!isInImageBounds(nat.x, nat.y)) return;
            state.boxStartX = nat.x;
            state.boxStartY = nat.y;
            state.boxCurrentX = nat.x;
            state.boxCurrentY = nat.y;
        }
    });

    // Window-level mousemove for panning and box drawing outside canvas
    window.addEventListener("mousemove", function (e) {
        // Handle panning
        if (state.isPanning) {
            var dx = e.clientX - state.panStartX;
            var dy = e.clientY - state.panStartY;

            if (!state.didDrag && (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD)) {
                state.didDrag = true;
            }

            if (state.didDrag && state.zoom > 1) {
                var rect = getCanvasDisplayRect();
                var cssToCanvasX = canvas.width / rect.width;
                var cssToCanvasY = canvas.height / rect.height;
                state.panX = state.panStartPanX + dx * cssToCanvasX;
                state.panY = state.panStartPanY + dy * cssToCanvasY;
                clampPan();
                requestRender();
            }
            return;
        }

        // Handle box drawing (works both inside and outside canvas)
        if (state.mouseDownButton === 0 && !isMoveModeActive()) {
            var dragDist = Math.sqrt(
                Math.pow(e.clientX - state.mouseDownX, 2) +
                Math.pow(e.clientY - state.mouseDownY, 2)
            );
            if (dragDist > DRAG_THRESHOLD) {
                state.didDrag = true;
                state.isDrawingBox = true;
            }
            if (state.isDrawingBox) {
                var natCur = clientToNatural(e.clientX, e.clientY);
                state.boxCurrentX = Math.max(0, Math.min(natCur.x, state.naturalWidth));
                state.boxCurrentY = Math.max(0, Math.min(natCur.y, state.naturalHeight));
                requestRender();
            }
        }
    });

    // Window-level mouseup for panning and box drawing
    window.addEventListener("mouseup", function (e) {
        if (state.isPanning && (e.button === 0 || e.button === 1)) {
            state.isPanning = false;
            updateCanvasCursor();
        }

        // Finalize box drawing if mouse released outside canvas
        if (e.button === 0 && state.isDrawingBox && state.didDrag) {
            addBox(state.boxStartX, state.boxStartY, state.boxCurrentX, state.boxCurrentY);
        }

        // Clean up interaction state (no-op if canvas handler already reset)
        if (e.button === state.mouseDownButton) {
            state.isDrawingBox = false;
            state.didDrag = false;
            state.mouseDownButton = -1;
        }
    });

    // Canvas-local mousemove for coord display, alt-hover, and box drawing
    canvas.addEventListener("mousemove", function (e) {
        if (!state.image) return;
        if (state.isPanning) return;

        // Update coord display
        var nat = clientToNatural(e.clientX, e.clientY);
        if (isInImageBounds(nat.x, nat.y)) {
            coordDisplay.textContent = Math.round(nat.x) + ", " + Math.round(nat.y);
        } else {
            coordDisplay.textContent = "";
        }

        // Move mode: no alt-hover or box drawing
        if (isMoveModeActive()) return;

        // Alt+hover: highlight nearest point or box for deletion
        if (e.altKey && !state.isDrawingBox) {
            var hoverPtIdx = -1;
            var hoverBoxIdx = -1;
            if (isInImageBounds(nat.x, nat.y)) {
                var ptIdx = findNearestPoint(nat.x, nat.y);
                var ptDist = Infinity;
                if (ptIdx >= 0) {
                    var hp = state.objects[state.activeObjectIndex].points[ptIdx];
                    ptDist = Math.sqrt((hp[0] - nat.x) * (hp[0] - nat.x) + (hp[1] - nat.y) * (hp[1] - nat.y));
                }
                var boxResult = findNearestBox(nat.x, nat.y);
                if (ptIdx >= 0 && boxResult.index >= 0) {
                    if (ptDist <= boxResult.dist) {
                        hoverPtIdx = ptIdx;
                    } else {
                        hoverBoxIdx = boxResult.index;
                    }
                } else if (ptIdx >= 0) {
                    hoverPtIdx = ptIdx;
                } else if (boxResult.index >= 0) {
                    hoverBoxIdx = boxResult.index;
                }
            }
            var changed = false;
            if (hoverPtIdx !== state.altHoverPointIndex) {
                state.altHoverPointIndex = hoverPtIdx;
                changed = true;
            }
            if (hoverBoxIdx !== state.altHoverBoxIndex) {
                state.altHoverBoxIndex = hoverBoxIdx;
                changed = true;
            }
            if (changed) requestRender();
            canvas.style.cursor = (hoverPtIdx >= 0 || hoverBoxIdx >= 0) ? "not-allowed" : "crosshair";
        } else if (state.altHoverPointIndex >= 0 || state.altHoverBoxIndex >= 0) {
            state.altHoverPointIndex = -1;
            state.altHoverBoxIndex = -1;
            canvas.style.cursor = "crosshair";
            requestRender();
        }

        // Box drawing mousemove is handled by window-level handler
    });

    canvas.addEventListener("mouseup", function (e) {
        if (!state.image) return;

        // Pan ended via window handler; skip prompt actions in move mode
        if (isMoveModeActive()) return;

        // Alt+click → delete nearest point or box
        if (e.altKey && (e.button === 0 || e.button === 2) && !state.didDrag) {
            var natAlt = clientToNatural(e.clientX, e.clientY);
            if (isInImageBounds(natAlt.x, natAlt.y)) {
                var delPtIdx = findNearestPoint(natAlt.x, natAlt.y);
                var delPtDist = Infinity;
                if (delPtIdx >= 0) {
                    var dp = state.objects[state.activeObjectIndex].points[delPtIdx];
                    delPtDist = Math.sqrt((dp[0] - natAlt.x) * (dp[0] - natAlt.x) + (dp[1] - natAlt.y) * (dp[1] - natAlt.y));
                }
                var delBoxResult = findNearestBox(natAlt.x, natAlt.y);
                if (delPtIdx >= 0 && delBoxResult.index >= 0) {
                    if (delPtDist <= delBoxResult.dist) {
                        deletePointAt(delPtIdx);
                    } else {
                        deleteBoxAt(delBoxResult.index);
                    }
                } else if (delPtIdx >= 0) {
                    deletePointAt(delPtIdx);
                } else if (delBoxResult.index >= 0) {
                    deleteBoxAt(delBoxResult.index);
                }
                state.altHoverPointIndex = -1;
                state.altHoverBoxIndex = -1;
            }
            state.isDrawingBox = false;
            state.didDrag = false;
            state.mouseDownButton = -1;
            return;
        }

        if (e.button === 0) {
            if (state.isDrawingBox && state.didDrag) {
                // Finalize box
                addBox(state.boxStartX, state.boxStartY, state.boxCurrentX, state.boxCurrentY);
            } else if (!state.didDrag) {
                // Left click → fg point
                var nat = clientToNatural(e.clientX, e.clientY);
                if (isInImageBounds(nat.x, nat.y)) {
                    addPoint(nat.x, nat.y, 1);
                }
            }
            state.isDrawingBox = false;
            state.didDrag = false;
            state.mouseDownButton = -1;
        } else if (e.button === 2) {
            // Right click → bg point
            if (!state.didDrag) {
                var natR = clientToNatural(e.clientX, e.clientY);
                if (isInImageBounds(natR.x, natR.y)) {
                    addPoint(natR.x, natR.y, 0);
                }
            }
            state.mouseDownButton = -1;
        }
    });

    canvas.addEventListener("mouseleave", function () {
        coordDisplay.textContent = "";
        if (state.altHoverPointIndex >= 0 || state.altHoverBoxIndex >= 0) {
            state.altHoverPointIndex = -1;
            state.altHoverBoxIndex = -1;
            requestRender();
        }
        // Don't cancel pan or box drawing — window handlers will finish them
    });

    canvas.addEventListener("contextmenu", function (e) {
        e.preventDefault();
    });

    // Double-click to reset zoom (only in move mode)
    canvas.addEventListener("dblclick", function (e) {
        if (!state.image) return;
        if (!isMoveModeActive()) return;
        e.preventDefault();
        resetZoom();
        updateCanvasCursor();
    });

    document.addEventListener("keyup", function (e) {
        if (e.key === " ") {
            state.spaceHeld = false;
            updateCanvasCursor();
            renderToolbar();
        }
        if (e.key === "Alt" && (state.altHoverPointIndex >= 0 || state.altHoverBoxIndex >= 0)) {
            state.altHoverPointIndex = -1;
            state.altHoverBoxIndex = -1;
            updateCanvasCursor();
            requestRender();
        }
    });

    // --- Zoom ---

    canvas.addEventListener("wheel", function (e) {
        if (!state.image) return;
        e.preventDefault();

        var delta = e.deltaY;
        if (e.deltaMode === 1) delta *= 16;
        else if (e.deltaMode === 2) delta *= 100;

        var newZoom = state.zoom * (1 - delta * ZOOM_SENSITIVITY);
        newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, newZoom));

        // Zoom toward cursor position
        var rect = getCanvasDisplayRect();
        var mx = (e.clientX - rect.left) * (canvas.width / rect.width);
        var my = (e.clientY - rect.top) * (canvas.height / rect.height);

        state.panX = mx - (mx - state.panX) * (newZoom / state.zoom);
        state.panY = my - (my - state.panY) * (newZoom / state.zoom);
        state.zoom = newZoom;
        clampPan();
        updateCanvasCursor();
        requestRender();
    }, { passive: false });

    // --- Keyboard shortcuts ---

    // Track hover state so shortcuts work without requiring element focus.
    // Listening on document level avoids the Gradio focus-management issue
    // where container.focus() is ineffective after canvas clicks.
    var _mouseOverContainer = false;
    container.addEventListener("mouseenter", function () { _mouseOverContainer = true; });
    container.addEventListener("mouseleave", function () { _mouseOverContainer = false; });

    document.addEventListener("keydown", function (e) {
        // Only handle when mouse is over this container — but always
        // allow Escape while drawing a box (mouse may be outside canvas).
        if (!_mouseOverContainer && !(e.key === "Escape" && state.isDrawingBox)) return;

        // Ignore if inside a text-like input or textarea (not range sliders)
        if (e.target.tagName === "TEXTAREA") return;
        if (e.target.tagName === "INPUT" && e.target.type !== "range") return;

        // Space hold → temporary move mode
        if (e.key === " ") {
            e.preventDefault();
            if (!e.repeat) {
                state.spaceHeld = true;
                updateCanvasCursor();
                renderToolbar();
            }
            return;
        }

        var key = e.key;

        // Number keys 1-8: switch object
        if (key >= "1" && key <= "8") {
            var idx = parseInt(key, 10) - 1;
            if (idx < state.objects.length) {
                state.activeObjectIndex = idx;
                renderToolbar();
                requestRender();
            }
            e.preventDefault();
            return;
        }

        switch (key.toLowerCase()) {
            case "n":
                addObject();
                e.preventDefault();
                break;
            case "z":
                undoLastPrompt();
                e.preventDefault();
                break;
            case "m":
                state.showMasks = !state.showMasks;
                renderToolbar();
                requestRender();
                e.preventDefault();
                break;
            case "v":
                state.settingsVisible = !state.settingsVisible;
                syncVisibility();
                e.preventDefault();
                break;
            case "h":
                state.objects[state.activeObjectIndex].visible = !state.objects[state.activeObjectIndex].visible;
                renderToolbar();
                requestRender();
                e.preventDefault();
                break;
            case "i":
                state.showImage = !state.showImage;
                renderToolbar();
                requestRender();
                e.preventDefault();
                break;
            case "c":
                state.cutoutMode = !state.cutoutMode;
                renderToolbar();
                requestRender();
                e.preventDefault();
                break;
            case "delete":
            case "backspace":
                deleteObject(state.activeObjectIndex);
                e.preventDefault();
                break;
            case "?":
                helpOverlay.classList.toggle("hidden");
                e.preventDefault();
                break;
            case "f":
                toggleMaximize();
                e.preventDefault();
                break;
            case "escape":
                if (state.isDrawingBox) {
                    state.isDrawingBox = false;
                    // Reset mouseDownButton so window mousemove won't
                    // re-enable isDrawingBox.  Keep didDrag=true so the
                    // subsequent mouseup is treated as a drag (no-op)
                    // rather than a click that would add a point.
                    state.mouseDownButton = -1;
                    requestRender();
                } else if (state.maximized) {
                    toggleMaximize();
                } else {
                    helpOverlay.classList.add("hidden");
                }
                e.preventDefault();
                break;
            case "+":
            case "=":
                zoomToCenter(state.zoom * 1.25);
                e.preventDefault();
                break;
            case "-":
                zoomToCenter(state.zoom / 1.25);
                e.preventDefault();
                break;
            case "0":
                resetZoom();
                updateCanvasCursor();
                e.preventDefault();
                break;
        }
    });

    // --- Button events ---

    addObjectBtn.addEventListener("click", function () { addObject(); });
    moveBtn.addEventListener("click", function () {
        state.moveMode = !state.moveMode;
        updateCanvasCursor();
        renderToolbar();
    });
    undoBtn.addEventListener("click", function () { undoLastPrompt(); });
    clearBtn.addEventListener("click", function () { clearActiveObject(); });
    clearAllBtn.addEventListener("click", function () { clearAll(); });
    maskToggleBtn.addEventListener("click", function () {
        state.showMasks = !state.showMasks;
        renderToolbar();
        requestRender();
    });
    maximizeBtn.addEventListener("click", function () { toggleMaximize(); });
    helpBtn.addEventListener("click", function () { helpOverlay.classList.toggle("hidden"); });
    helpCloseBtn.addEventListener("click", function () { helpOverlay.classList.add("hidden"); });

    // Settings panel
    settingsBtn.addEventListener("click", function () {
        state.settingsVisible = !state.settingsVisible;
        syncVisibility();
    });
    pointSizeSlider.addEventListener("input", function () {
        pointRadius = parseInt(pointSizeSlider.value, 10);
        pointSizeValue.textContent = pointRadius;
        requestRender();
    });
    maskOpacitySlider.addEventListener("input", function () {
        maskAlpha = parseInt(maskOpacitySlider.value, 10) / 100;
        maskOpacityValue.textContent = parseInt(maskOpacitySlider.value, 10) + "%";
        requestRender();
    });
    boxLineWidthSlider.addEventListener("input", function () {
        boxLineWidth = parseFloat(boxLineWidthSlider.value);
        boxLineWidthValue.textContent = boxLineWidth + "px";
        requestRender();
    });
    imageToggleBtn.addEventListener("click", function () {
        state.showImage = !state.showImage;
        renderToolbar();
        requestRender();
    });
    cutoutBtn.addEventListener("click", function () {
        state.cutoutMode = !state.cutoutMode;
        renderToolbar();
        requestRender();
    });

    function clearImage() {
        if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);
        state.image = null;
        state.imageUrl = null;
        state.objectUrl = null;
        state.filePath = null;
        state.pendingEmit = false;
        state.imageSource = null;
        state.rawMasks = [];
        state.maskCanvases = [];
        state.objects = [createEmptyObject(0)];
        state.activeObjectIndex = 0;
        state.zoom = 1;
        state.panX = 0;
        state.panY = 0;
        state.moveMode = false;
        state.cutoutMode = false;
        state.isProcessing = false;
        if (state.maximized) {
            toggleMaximize();
        }
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        syncVisibility();
        renderToolbar();
        props.value = null;
        trigger("input");
    }

    clearImageBtn.addEventListener("click", function () { clearImage(); });

    // --- File upload (input) ---

    function uploadToServer(file) {
        var formData = new FormData();
        formData.append("files", file);
        var capturedUrl = state.objectUrl;

        fetch("/gradio_api/upload", { method: "POST", body: formData })
            .then(function (res) {
                if (!res.ok) throw new Error("Upload failed: " + res.status);
                return res.json();
            })
            .then(function (paths) {
                if (state.objectUrl !== capturedUrl) return;
                state.filePath = paths[0];
                if (state.pendingEmit) {
                    state.pendingEmit = false;
                    emitPromptData();
                }
            })
            .catch(function () {
                if (state.objectUrl !== capturedUrl) return;
            });
    }

    function loadImageFile(file) {
        if (!file || !file.type.startsWith("image/")) return;

        // Revoke previous blob URL
        if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);

        var url = URL.createObjectURL(file);
        state.objectUrl = url;
        state.filePath = null;
        state.pendingEmit = false;
        state.imageSource = "upload";
        state.imageUrl = null;
        state.rawMasks = [];
        state.maskCanvases = [];

        var img = new Image();
        img.onload = function () {
            state.image = img;
            state.naturalWidth = img.naturalWidth;
            state.naturalHeight = img.naturalHeight;
            state.objects = [createEmptyObject(0)];
            state.activeObjectIndex = 0;
            state.zoom = 1;
            state.panX = 0;
            state.panY = 0;
            resizeCanvas();
            renderToolbar();
            requestRender();
            emitPromptData();
        };
        img.src = url;

        uploadToServer(file);
    }

    fileInput.addEventListener("change", function () {
        if (fileInput.files && fileInput.files[0]) {
            loadImageFile(fileInput.files[0]);
            fileInput.value = "";
        }
    });

    dropZone.addEventListener("dragover", function (e) {
        e.preventDefault();
        dropZone.classList.add("drag-over");
    });

    dropZone.addEventListener("dragleave", function () {
        dropZone.classList.remove("drag-over");
    });

    dropZone.addEventListener("drop", function (e) {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
        var files = e.dataTransfer && e.dataTransfer.files;
        if (files && files[0]) {
            loadImageFile(files[0]);
        }
    });

    // Also allow drop on the whole container when image is loaded
    container.addEventListener("dragover", function (e) {
        e.preventDefault();
    });

    container.addEventListener("drop", function (e) {
        e.preventDefault();
        var files = e.dataTransfer && e.dataTransfer.files;
        if (files && files[0] && files[0].type.startsWith("image/")) {
            loadImageFile(files[0]);
        }
    });

    // --- Resize ---

    var resizeObserver = new ResizeObserver(function () {
        if (state.image) {
            resizeCanvas();
            requestRender();
        }
    });
    resizeObserver.observe(canvasWrapper);

    // --- Init ---

    renderToolbar();
    handleDataUpdate();

})();
