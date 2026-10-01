"""
FutureForge — Real 3D Neural Orb (Three.js)
--------------------------------------------
Renders an actual WebGL 3D object (not a CSS/SVG gauge): a wireframe
icosahedron "core", an outer point-cloud shell, and dynamically drawn
synapse lines between nearby particles — pulsing and color-shifting
with the user's live focus score. Auto-rotates, responds to drag/scroll,
and is fully theme-aware (dark / light).
"""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components


def _band_colors(score: float) -> dict:
    """Pick a color ramp consistent with the rest of the app's badge system."""
    if score >= 75:
        return {"core": "0x34d399", "glow": "0x6ee7b7", "spark": "0xa7f3d0"}
    if score >= 55:
        return {"core": "0xfbbf24", "glow": "0xfcd34d", "spark": "0xfde68a"}
    return {"core": "0xf87171", "glow": "0xfca5a5", "spark": "0xfecaca"}


def render_orb(
    score: float = 70.0,
    label: str = "Focus",
    height: int = 340,
    theme: str = "dark",
    key: str = "orb",
) -> None:
    """Draws a real, interactive 3D neural orb sized to `height` px.

    score: 0-100, drives color band + pulse intensity + rotation speed
    theme: 'dark' | 'light' — controls background/particle contrast
    """
    colors = _band_colors(score)
    bg = "transparent"
    line_alpha = 0.55 if theme == "dark" else 0.35
    particle_size = 2.6
    cfg = json.dumps(
        {
            "score": max(0, min(100, score)),
            "label": label,
            "core": colors["core"],
            "glow": colors["glow"],
            "spark": colors["spark"],
            "lineAlpha": line_alpha,
            "particleSize": particle_size,
            "theme": theme,
        }
    )

    html = f"""
    <style>
      #orb-wrap-{key} {{ width:100%; height:{height}px; height:min({height}px, 82vw); position:relative;
           border-radius:22px; overflow:hidden; background:{bg}; }}
      #orb-canvas-{key} {{ width:100%; height:100%; display:block; cursor:grab; touch-action:none; }}
      #orb-label-{key} {{ position:absolute; bottom:14px; left:0; right:0; text-align:center;
           font-family:'Space Grotesk',sans-serif; font-size:0.78rem; letter-spacing:1.5px; text-transform:uppercase;
           color: rgba(180,190,230,0.75); pointer-events:none; padding: 0 8px; }}
      @media (max-width: 380px) {{
        #orb-wrap-{key} {{ border-radius:16px; }}
        #orb-label-{key} {{ font-size:0.66rem; letter-spacing:1px; bottom:10px; }}
        .orb-hint-{key} {{ display:none; }}
      }}
    </style>
    <div id="orb-wrap-{key}">
      <canvas id="orb-canvas-{key}"></canvas>
      <div id="orb-label-{key}">
        {label} · {score:.0f}/100 <span class="orb-hint-{key}">· drag to rotate</span>
      </div>
    </div>

    <script src="https://unpkg.com/three@0.160.0/build/three.min.js"></script>
    <script>
    (function() {{
      const CFG = {cfg};
      const wrap = document.getElementById("orb-wrap-{key}");
      const canvas = document.getElementById("orb-canvas-{key}");

      function boot() {{
        if (typeof THREE === "undefined") {{ setTimeout(boot, 60); return; }}

        let W = wrap.clientWidth || 400, H = wrap.clientHeight || {height};

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 100);
        camera.position.set(0, 0, 6.2);

        const renderer = new THREE.WebGLRenderer({{ canvas: canvas, antialias: true, alpha: true }});
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.setSize(W, H);

        const group = new THREE.Group();
        scene.add(group);

        // --- Wireframe icosahedron "neural core" -----------------------------------
        const coreGeo = new THREE.IcosahedronGeometry(1.55, 2);
        const coreMat = new THREE.MeshBasicMaterial({{
          color: parseInt(CFG.core), wireframe: true, transparent: true, opacity: 0.85,
        }});
        const coreMesh = new THREE.Mesh(coreGeo, coreMat);
        group.add(coreMesh);

        // Soft inner glow sphere
        const glowGeo = new THREE.IcosahedronGeometry(1.35, 1);
        const glowMat = new THREE.MeshBasicMaterial({{
          color: parseInt(CFG.glow), transparent: true, opacity: 0.06,
        }});
        group.add(new THREE.Mesh(glowGeo, glowMat));

        // --- Outer particle shell (neurons) -----------------------------------------
        const NUM_PTS = 130;
        const radius = 2.35;
        const positions = new Float32Array(NUM_PTS * 3);
        const basePositions = new Float32Array(NUM_PTS * 3);
        for (let i = 0; i < NUM_PTS; i++) {{
          // Fibonacci sphere distribution for even coverage
          const y = 1 - (i / (NUM_PTS - 1)) * 2;
          const r = Math.sqrt(1 - y * y);
          const theta = Math.PI * (1 + Math.sqrt(5)) * i;
          const x = Math.cos(theta) * r;
          const z = Math.sin(theta) * r;
          positions[i * 3] = x * radius;
          positions[i * 3 + 1] = y * radius;
          positions[i * 3 + 2] = z * radius;
          basePositions[i * 3] = positions[i * 3];
          basePositions[i * 3 + 1] = positions[i * 3 + 1];
          basePositions[i * 3 + 2] = positions[i * 3 + 2];
        }}
        const ptsGeo = new THREE.BufferGeometry();
        ptsGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        const ptsMat = new THREE.PointsMaterial({{
          color: parseInt(CFG.spark), size: CFG.particleSize * 0.045, sizeAttenuation: true, transparent: true, opacity: 0.95,
        }});
        const points = new THREE.Points(ptsGeo, ptsMat);
        group.add(points);

        // --- Synapse lines: connect nearby neurons ----------------------------------
        const lineMat = new THREE.LineBasicMaterial({{
          color: parseInt(CFG.core), transparent: true, opacity: CFG.lineAlpha * 0.5,
        }});
        const maxDist = 0.95;
        const linePositions = [];
        for (let i = 0; i < NUM_PTS; i++) {{
          for (let j = i + 1; j < NUM_PTS; j++) {{
            const dx = basePositions[i*3] - basePositions[j*3];
            const dy = basePositions[i*3+1] - basePositions[j*3+1];
            const dz = basePositions[i*3+2] - basePositions[j*3+2];
            const d = Math.sqrt(dx*dx + dy*dy + dz*dz);
            if (d < maxDist) {{
              linePositions.push(basePositions[i*3], basePositions[i*3+1], basePositions[i*3+2]);
              linePositions.push(basePositions[j*3], basePositions[j*3+1], basePositions[j*3+2]);
            }}
          }}
        }}
        const lineGeo = new THREE.BufferGeometry();
        lineGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(linePositions), 3));
        const lines = new THREE.LineSegments(lineGeo, lineMat);
        group.add(lines);

        // --- Ambient point light for subtle shading on core -------------------------
        const light = new THREE.PointLight(parseInt(CFG.glow), 1.2, 20);
        light.position.set(3, 3, 5);
        scene.add(light);
        scene.add(new THREE.AmbientLight(0xffffff, 0.25));

        // --- Drag-to-rotate (pointer events, no OrbitControls dependency) ----------
        let dragging = false, lastX = 0, lastY = 0;
        let rotY = 0, rotX = 0.15;
        let autoSpeed = 0.0016 + (CFG.score / 100) * 0.0026;

        function onDown(e) {{
          dragging = true; canvas.style.cursor = "grabbing";
          const p = e.touches ? e.touches[0] : e;
          lastX = p.clientX; lastY = p.clientY;
        }}
        function onMove(e) {{
          if (!dragging) return;
          const p = e.touches ? e.touches[0] : e;
          const dx = p.clientX - lastX, dy = p.clientY - lastY;
          rotY += dx * 0.005;
          rotX += dy * 0.005;
          rotX = Math.max(-1.2, Math.min(1.2, rotX));
          lastX = p.clientX; lastY = p.clientY;
        }}
        function onUp() {{ dragging = false; canvas.style.cursor = "grab"; }}

        canvas.addEventListener("mousedown", onDown);
        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
        canvas.addEventListener("touchstart", onDown, {{passive: true}});
        window.addEventListener("touchmove", onMove, {{passive: true}});
        window.addEventListener("touchend", onUp);

        // --- Resize handling ----------------------------------------------------
        function resize() {{
          W = wrap.clientWidth || W; H = wrap.clientHeight || H;
          camera.aspect = W / H; camera.updateProjectionMatrix();
          renderer.setSize(W, H);
        }}
        window.addEventListener("resize", resize);

        // --- Animation loop: pulse + gentle vertex noise (organic "neural" feel) ---
        const clock = new THREE.Clock();
        function animate() {{
          requestAnimationFrame(animate);
          const t = clock.getElapsedTime();

          if (!dragging) {{ rotY += autoSpeed; }}
          group.rotation.y = rotY;
          group.rotation.x = rotX;

          // Pulse core scale with score-driven breathing rhythm
          const pulse = 1 + Math.sin(t * (1.1 + CFG.score/140)) * 0.045;
          coreMesh.scale.setScalar(pulse);

          // Organic jitter on outer particles (cheap pseudo-noise via sines)
          const posAttr = ptsGeo.attributes.position;
          for (let i = 0; i < NUM_PTS; i++) {{
            const bx = basePositions[i*3], by = basePositions[i*3+1], bz = basePositions[i*3+2];
            const n = Math.sin(t * 0.8 + i * 0.37) * 0.05 + Math.cos(t * 0.5 + i * 0.19) * 0.04;
            posAttr.array[i*3]   = bx * (1 + n * 0.5);
            posAttr.array[i*3+1] = by * (1 + n * 0.5);
            posAttr.array[i*3+2] = bz * (1 + n * 0.5);
          }}
          posAttr.needsUpdate = true;

          lineMat.opacity = CFG.lineAlpha * (0.35 + Math.sin(t * 1.4) * 0.15 + 0.2);

          renderer.render(scene, camera);
        }}
        animate();
      }}
      boot();
    }})();
    </script>
    """

    components.html(html, height=height + 10, scrolling=False)
