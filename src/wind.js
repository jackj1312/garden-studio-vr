/* ------------------------------------------------------------------ *
 *  Wind. Vertex sway injected into standard materials, so grass and
 *  foliage move without a second shader to maintain. Movement is one
 *  of the strongest presence cues there is: a garden where nothing
 *  stirs reads as a diorama.
 *
 *  Sway scales with height squared, so roots stay planted and tips
 *  move most. Works for instanced grass (reads the instance position
 *  so neighbours are out of phase) and for ordinary meshes.
 * ------------------------------------------------------------------ */

const swaying = [];

export function addWind(material, { strength = 0.05, speed = 1.2, height = 1.0 } = {}) {
  const prior = material.onBeforeCompile;                 // keep whatever the material already injects
  const priorKey = material.customProgramCacheKey;
  material.onBeforeCompile = shader => {
    if (prior) prior.call(material, shader);
    shader.uniforms.uTime = { value: 0 };
    shader.uniforms.uStrength = { value: strength };
    shader.uniforms.uSpeed = { value: speed };
    shader.uniforms.uHeight = { value: height };
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>",
        "#include <common>\nuniform float uTime;\nuniform float uStrength;\nuniform float uSpeed;\nuniform float uHeight;")
      .replace("#include <begin_vertex>", `#include <begin_vertex>
        {
          vec3 wp = (modelMatrix * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
          #ifdef USE_INSTANCING
            wp += (instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
          #endif
          wp += position * 0.35;
          float h = clamp(position.y / uHeight, 0.0, 1.0);
          h *= h;
          float g1 = sin(uTime * uSpeed + wp.x * 0.7 + wp.z * 0.9);
          float g2 = sin(uTime * uSpeed * 1.7 + wp.x * 1.3 - wp.z * 0.6) * 0.5;
          transformed.x += (g1 + g2) * uStrength * h;
          transformed.z += g2 * uStrength * 0.6 * h;
        }`);
    material.userData.shader = shader;
  };
  material.customProgramCacheKey = () => `${priorKey ? priorKey.call(material) : ""}|wind-${strength}-${speed}-${height}`;
  swaying.push(material);
  return material;
}

export function updateWind(seconds) {
  for (const m of swaying) {
    const s = m.userData.shader;
    if (s) s.uniforms.uTime.value = seconds;
  }
}
