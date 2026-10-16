# Third-party components

The repository contains application source and metadata. Model weights and native
runtime binaries are downloaded during setup and excluded from Git. The MIT
license for this application does not replace their licenses.

| Component | Source / pinned selection | License information |
| --- | --- | --- |
| FunASR native runtime | [modelscope/FunASR, runtime-llamacpp-v0.2.1](https://github.com/modelscope/FunASR/releases/tag/runtime-llamacpp-v0.2.1) | [FunASR license](https://github.com/modelscope/FunASR/blob/runtime-llamacpp-v0.2.1/LICENSE); review nested runtime dependencies |
| Fun-ASR Nano GGUF encoder and Q5_K_M decoder | [FunAudioLLM/Fun-ASR-Nano-GGUF](https://huggingface.co/FunAudioLLM/Fun-ASR-Nano-GGUF/tree/46e849502a867080d66d351b8dfb1018b607e509) | Use the model card and original model terms; includes a Qwen3-derived decoder |
| FSMN-VAD GGUF | [FunAudioLLM/fsmn-vad-GGUF](https://huggingface.co/FunAudioLLM/fsmn-vad-GGUF/tree/6840bae4c5c92ee8c04faaf4db23dd0105098d7f) | See model card and upstream model terms |
| Silero VAD v6.2.0, converted for whisper.cpp | [ggml-org/whisper-vad](https://huggingface.co/ggml-org/whisper-vad/tree/9ffd54a1e1ee413ddf265af9913beaf518d1639b) | See model card and [Silero VAD license](https://github.com/snakers4/silero-vad/blob/master/LICENSE) |
| whisper.cpp VAD executable and libraries | [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp), installed through Homebrew | [MIT license](https://github.com/ggml-org/whisper.cpp/blob/master/LICENSE) |
| PyObjC | [PyObjC](https://github.com/ronaldoussoren/pyobjc) | [License](https://github.com/ronaldoussoren/pyobjc/blob/main/pyobjc-core/License.txt) |
| Pyperclip | [Pyperclip](https://github.com/asweigart/pyperclip) | [License](https://github.com/asweigart/pyperclip/blob/master/LICENSE.txt) |
| PyInstaller and bootloader | [PyInstaller](https://github.com/pyinstaller/pyinstaller) | [License and distribution exception](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt) |
| Python | [Python](https://www.python.org) | [PSF license](https://docs.python.org/3/license.html) |

Exact download URLs, revisions and SHA-256 values are in `runtime-manifest.json`.
The whisper.cpp formula is resolved from the user's Homebrew installation rather
than pinned to one machine's Cellar version; native library behavior can therefore
vary between installations.

Before distributing a full `.app` or release archive, include the required license
texts and notices for the actual bundled dependencies and weights, and verify
their distribution conditions. The current source publication does not provide
a reviewed or notarized binary release.
