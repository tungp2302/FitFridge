// Barcode-Scanner: nutzt die native BarcodeDetector-API (Android/macOS) und
// faellt sonst auf zxing-wasm zurueck (Windows-Desktop, Firefox, iOS).
(function () {
  const NATIVE_FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128'];
  const ZXING_FORMATS = ['EAN-13', 'EAN-8', 'UPC-A', 'UPC-E', 'Code128'];

  let detector = null;   // native BarcodeDetector, sonst null
  let zxingRead = null;  // zxing-wasm readBarcodes als Fallback

  async function ensureDecoder() {
    if ('BarcodeDetector' in window) {
      detector = new BarcodeDetector({ formats: NATIVE_FORMATS });
      return true;
    }
    try {
      ({ readBarcodes: zxingRead } = await import('https://esm.run/zxing-wasm/reader'));
      return true;
    } catch (err) {
      return false;
    }
  }

  // Graustufen + Kontrast strecken (Auto-Levels, 1%-Clipping gegen Glanz/Ausreisser).
  function enhanceContrast(image) {
    const d = image.data;
    const hist = new Uint32Array(256);
    for (let i = 0; i < d.length; i += 4) {
      const g = (d[i] * 0.299 + d[i + 1] * 0.587 + d[i + 2] * 0.114) | 0;
      d[i] = d[i + 1] = d[i + 2] = g;
      hist[g] += 1;
    }
    const clip = (d.length / 4) * 0.01;
    let lo = 0;
    let hi = 255;
    let acc = 0;
    while (lo < 255 && (acc += hist[lo]) <= clip) lo += 1;
    acc = 0;
    while (hi > 0 && (acc += hist[hi]) <= clip) hi -= 1;
    const scale = hi > lo ? 255 / (hi - lo) : 1;
    for (let i = 0; i < d.length; i += 4) {
      d[i] = d[i + 1] = d[i + 2] = Math.max(0, Math.min(255, (d[i] - lo) * scale));
    }
    return image;
  }

  // Erkannte Code-Strings des aktuellen Frames (oder []).
  async function detectFrame(video, canvas) {
    if (detector) {
      return (await detector.detect(video)).map((c) => c.rawValue);
    }
    const w = video.videoWidth;
    const h = video.videoHeight;
    if (!w || !h) return [];
    const bandH = Math.round(h * 0.55);   // nur das mittlere Band (1D-Barcodes sind breit)
    canvas.width = w;
    canvas.height = bandH;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(video, 0, (h - bandH) / 2, w, bandH, 0, 0, w, bandH);
    const image = enhanceContrast(ctx.getImageData(0, 0, w, bandH));
    const results = await zxingRead(image, {
      tryHarder: true, tryRotate: true, tryInvert: true, tryDownscale: true,
      formats: ZXING_FORMATS, maxNumberOfSymbols: 1,
    });
    return results.map((r) => r.text).filter(Boolean);
  }

  // onResult(code) wird mit dem ersten erkannten Barcode aufgerufen.
  window.startBarcodeScan = async function (onResult) {
    if (!(await ensureDecoder())) {
      alert('Scanner konnte nicht geladen werden. Internetverbindung pruefen oder Barcode eintippen.');
      return;
    }

    const overlay = document.createElement('div');
    overlay.className = 'barcode-scanner';
    overlay.innerHTML = `
      <div class="barcode-scanner__frame">
        <video class="barcode-scanner__video" playsinline muted></video>
        <div class="barcode-scanner__reticle"></div>
      </div>
      <p class="barcode-scanner__hint">Barcode scharf und formatfuellend in den Rahmen halten…</p>
      <button type="button" class="barcode-scanner__close">Abbrechen</button>`;
    document.body.appendChild(overlay);

    const video = overlay.querySelector('.barcode-scanner__video');
    const canvas = document.createElement('canvas');
    let stream = null;
    let done = false;

    function stop() {
      if (done) return;
      done = true;
      if (stream) stream.getTracks().forEach((track) => track.stop());
      overlay.remove();
    }
    overlay.querySelector('.barcode-scanner__close').addEventListener('click', stop);

    try {
      // Rueckkamera bevorzugen, hohe Aufloesung hilft beim Dekodieren.
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } },
      });
    } catch (err) {
      stop();
      alert('Kamera konnte nicht geoeffnet werden. Zugriff erlauben und ueber HTTPS aufrufen.');
      return;
    }
    video.srcObject = stream;
    await video.play();

    // Autofokus erzwingen, falls die Kamera ihn anbietet (gegen Unschaerfe).
    const [track] = stream.getVideoTracks();
    const caps = track.getCapabilities ? track.getCapabilities() : {};
    if (caps.focusMode && caps.focusMode.includes('continuous')) {
      track.applyConstraints({ advanced: [{ focusMode: 'continuous' }] }).catch(() => {});
    }

    // Frames pruefen, bis ein Code erkannt wird; naechster Tick erst nach der Analyse.
    async function tick() {
      if (done) return;
      try {
        const codes = await detectFrame(video, canvas);
        if (codes.length) { stop(); onResult(codes[0]); return; }
      } catch (err) {
        /* einzelne Frames duerfen fehlschlagen */
      }
      if (!done) setTimeout(tick, 200);
    }
    tick();
  };
})();
