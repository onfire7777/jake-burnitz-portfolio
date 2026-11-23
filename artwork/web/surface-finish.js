import { Matrix4, MeshPhysicalMaterial, MeshStandardMaterial } from "three";

// Put the finish in each manufactured part's coordinates. Blender's GLB
// packer can apply a scale and offset to individual primitives inside a part.
function brushFrame(mesh, root) {
  // The animated assemblies are the named, top-level glTF nodes. Their
  // local axes give a reel its true spindle and a plate its milling direction.
  let assembly = mesh;
  while (assembly.parent && assembly.parent !== root && assembly.parent.name !== "StudioObject") {
    assembly = assembly.parent;
  }
  return new Matrix4().copy(assembly.matrixWorld).invert().multiply(mesh.matrixWorld);
}

export function finishSurfaces(root) {
  root.updateWorldMatrix(true, true);
  root.traverse(mesh => {
    if (!mesh.isMesh) return;
    const space = brushFrame(mesh, root);
    function finish(base) {
      const name = base.name;
      const wound = /Magnetic tape|^Ferrite$/.test(name) && !root.getObjectByName("FilmAdvance");
      const metal = /aluminum|nickel|steel|Reel faces|Polished edge|ferrule|graphite|bead blast|Oxide green/i.test(name) && !/rubber/i.test(name);
      const enamel = /Signal enamel|Vermilion (lacquer|enamel)/i.test(name);
      if (!(metal || wound || enamel)) return base;
      let mat;
      if (enamel) {
        mat = new MeshPhysicalMaterial();
        MeshStandardMaterial.prototype.copy.call(mat, base);
        mat.metalness = .21;
        mat.roughness = .30;
        mat.clearcoat = .48;
        mat.clearcoatRoughness = .21;
      } else mat = base.clone();
      if (wound) { mat.metalness = .34; mat.roughness = .38; mat.color.multiplyScalar(1.16); }
      if (/bead blast|aluminum/i.test(name)) mat.roughness = Math.max(.33, mat.roughness);
      const finishKind = wound ? "winding" : metal ? "machining" : "lacquer";
      mat.customProgramCacheKey = () => "studio-material-" + finishKind;
      mat.onBeforeCompile = shader => {
        shader.uniforms.finishSpace = { value: space };
        shader.vertexShader = shader.vertexShader.replace("#include <common>",
          "#include <common>\nuniform mat4 finishSpace; varying vec3 studioP;")
          .replace("#include <begin_vertex>", "#include <begin_vertex>\nstudioP=(finishSpace*vec4(position,1.0)).xyz;");
        // At a distant camera angle, subpixel marks integrate to their average.
        // This keeps the grain attached to the part and prevents crawling lines.
        shader.fragmentShader = shader.fragmentShader.replace("#include <common>", `#include <common>
          varying vec3 studioP;
          float resolvedMark(float cycles) {
            return sin(6.2831853 * cycles) * (1.0 - smoothstep(.16, .55, fwidth(cycles)));
          }`);
        const coordinate = wound ? "length(studioP.xz)" : "studioP.z + studioP.y * .83";
        shader.fragmentShader = shader.fragmentShader.replace("#include <color_fragment>", `#include <color_fragment>
          float grainCoord = ${coordinate};
          float fine = resolvedMark(grainCoord * ${wound ? "48.0" : "64.0"} + .12 * sin(studioP.x * 11.0));
          float broad = resolvedMark(grainCoord * ${wound ? "17.0" : "19.0"} + .28 * sin(studioP.x * 4.3));
          diffuseColor.rgb *= 1.0 + fine * ${wound ? ".15" : ".013"} + broad * ${wound ? ".08" : ".008"};`)
          .replace("#include <roughnessmap_fragment>", `#include <roughnessmap_fragment>
          roughnessFactor = clamp(roughnessFactor + fine * ${wound ? ".10" : ".032"} + broad * .02, .15, .88);`)
          .replace("#include <normal_fragment_maps>", `#include <normal_fragment_maps>
            vec3 studioDX=dFdx(-vViewPosition), studioDY=dFdy(-vViewPosition);
            vec3 etchU=cross(studioDY,normal), etchV=cross(normal,studioDX);
            float etchArea=dot(studioDX,etchU);
            float etch=(fine+.48*broad)*${wound ? ".0014" : ".00015"};
            normal=normalize(max(abs(etchArea),1e-12)*normal-sign(etchArea)*(dFdx(etch)*etchU+dFdy(etch)*etchV));`);
      };
      return mat;
    }
    mesh.material = Array.isArray(mesh.material) ? mesh.material.map(finish) : finish(mesh.material);
  });
}
