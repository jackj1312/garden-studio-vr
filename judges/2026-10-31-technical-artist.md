# Judge 2 — real-time technical artist (31 Oct, after scanned trees + planting)

Verdict: the leaf shader never ran (addWind replaced onBeforeCompile), the Quest build is ~1M
triangles ×2 eyes + shadow pass with ~1.2 GB of uncompressed textures, and the stills show it.

1. Leaf shader: chain onBeforeCompile in addWind; translucency must use the shadowed
   directLight.color; faceDirection = 1.0 so bent normals survive back faces; bend plant normals
   up ~0.4; tint transmitted light yellow-green.
2. Quest: pick tier by device (OculusBrowser) and load only q; dispose the other set; KTX2
   textures (ETC1S diffuse/arm, UASTC normals); plants on Quest = 1k diffuse only; strip
   KHR_materials_specular/ior, COLOR_1, TEXCOORD_1; island_tree_01_q.glb still contains LOD0
   (1.5M tris) — strip it.
3. Budget: ≤250k tris and ~90 draw calls per eye on Quest. Trees as ~2k baked cluster cards
   (≤15k/tree); plants 0.8–1.5k each; near/far InstancedMesh split; limit plant scale by
   footprint radius (they spill onto the lawn); ground-cover card layer; mulch soil; per-instance
   hue/saturation jitter.
4. Shadows: on Quest render the shadow map once (fixed 20 m frustum, autoUpdate off) and give
   plants contact quads; on desktop shadow.radius 3–4, 4096 map, wind in a customDepthMaterial.
5. AA: composer has no MSAA target (antialias does nothing on desktop) — give it samples: 4;
   alphaToCoverage on all leaf materials (XR target already 4x).
6. Grass: makeGrass alphaMap bug cuts the dark halves of blades; normals up; blades 8–12 cm.
7. Sun counted twice: clamp the sun disc out of the EXR before PMREM, derive sun intensity from
   the removed energy, normalise after the clamp; hemi down to ≤0.15; night sky multiplier ~0.08.
8. AgX tone mapping, exposure ~1.3–1.5 midday; leaf envMapIntensity 0.9.
9. Haze: minimum veil 0.03–0.05 and sun-tinted fog; night on Quest = emissive fittings + light
   pools, ≤3 real lights; desktop 6–8 shadowless spots.
10. AO: per-vertex canopy occlusion in bendNormals; plant AO by height; baked lawn AO/shadow
    lightmap; GTAO half-res on standard desktop.
11. Octahedral impostors for far trees/hedge; delete leafTexture.
12. Bugs: VR exit never calls applyVRProfile(false); compileAsync after detail swap; skyTex
    never disposed (~220 MB); EXR as HalfFloatType; anisotropy 2 in VR; wind height per plant;
    branches need wind too.

Single change: chain the shader hook and use shadowed directLight with faceDirection 1.0.
