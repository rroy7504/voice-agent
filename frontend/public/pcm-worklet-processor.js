/**
 * AudioWorklet processor that captures mic audio, resamples to 16kHz,
 * and converts to Int16 PCM for sending to the backend.
 */
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = [];
    this.targetRate = 16000;
    this.bufferSize = 2048;
  }

  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;

    // Accumulate Float32 samples
    for (let i = 0; i < input.length; i++) {
      this.buffer.push(input[i]);
    }

    if (this.buffer.length >= this.bufferSize) {
      // Resample from device sampleRate to 16kHz
      const ratio = sampleRate / this.targetRate;
      const outputLen = Math.floor(this.buffer.length / ratio);
      const pcm16 = new Int16Array(outputLen);

      for (let i = 0; i < outputLen; i++) {
        const srcIdx = i * ratio;
        const floor = Math.floor(srcIdx);
        const frac = srcIdx - floor;
        const s0 = this.buffer[floor] || 0;
        const s1 = this.buffer[floor + 1] || 0;
        const sample = s0 * (1 - frac) + s1 * frac;
        pcm16[i] = Math.max(-32768, Math.min(32767, Math.round(sample * 32767)));
      }

      this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
      this.buffer = [];
    }

    return true;
  }
}

registerProcessor("pcm-processor", PCMProcessor);
