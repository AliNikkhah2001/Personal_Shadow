function addStripeFoilBlend(fragmentShader) {
  return fragmentShader;
}

function stripeFoilSettings(material) {
  return { enabled: false, opacity: 0, detail: 1 };
}

window.ShelfFoil = { addStripeFoilBlend, stripeFoilSettings };
