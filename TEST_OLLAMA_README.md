# Ollama LLM Test Scripts

Simple standalone scripts to test Ollama LLM locally. No project dependencies.

## Setup

### 1. Install Ollama
Download from: https://ollama.ai

### 2. Start Ollama Server
```bash
ollama serve
```
(Runs on `http://localhost:11434`)

### 3. Pull a Model
```bash
ollama pull mistral
# Or other models:
# ollama pull llama2
# ollama pull neural-chat
# ollama pull dolphin-mixtral
```

### 4. Install Python Requirements
```bash
pip install requests
```

## Scripts

### Option 1: Simple Non-Streaming
```bash
python test_ollama_simple.py
```
- Waits for full response before printing
- Clean output
- Good for testing

### Option 2: Streaming (Real-time)
```bash
python test_ollama_streaming.py
```
- Shows response as it's generated
- More interactive
- Better for long responses

## Configuration

Edit these in the scripts:
```python
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"  # Change this to your model

test_prompts = [
    "Your prompt here",
    "Add more prompts if needed",
]
```

## Available Models

Popular open-source models on Ollama:
- `mistral` - Fast, good quality
- `llama2` - Meta LLaMA 2 (7B, 13B, 70B)
- `neural-chat` - Intel neural chat
- `dolphin-mixtral` - Dolphin Mixtral
- `orca-mini` - Small, fast
- `codellama` - For code

Pull more: `ollama pull <model_name>`

## Troubleshooting

### "Cannot connect to Ollama"
- Make sure `ollama serve` is running
- Check if running on correct port (default 11434)

### "Model not found"
- Pull the model: `ollama pull <model_name>`
- Check available models: `ollama list`

### Slow response
- Try smaller model (orca-mini, neural-chat)
- Check GPU availability (some models use VRAM)

### Low quality response
- Try better model (mistral, llama2-13b)
- Adjust temperature (0.3 = more focused, 0.9 = more creative)

## Example Output

```
============================================================
🤖 OLLAMA LLM TEST SCRIPT
============================================================

Connecting to Ollama at: http://localhost:11434/api/generate
Using model: mistral

🧪 TEST 1: Simple Test
============================================================
Model: mistral
Prompt: Hãy giải thích cách để hạ nhiệt độ phòng?
============================================================

📡 Calling Ollama...

📝 Response:
------------------------------------------------------------
Có nhiều cách để hạ nhiệt độ phòng:

1. **Sử dụng quạt**: Quạt giúp lưu thông không khí...
2. **Mở cửa sổ**: Cho phép không khí lạnh từ bên ngoài...
...
```

## Tips

1. **Faster responses**: Use smaller models (orca-mini, neural-chat)
2. **Better quality**: Use larger models (mistral, llama2-13b, dolphin-mixtral)
3. **GPU acceleration**: Ollama automatically uses GPU if available
4. **Batch testing**: Uncomment multiple prompts in script
5. **Custom prompts**: Edit `test_prompts` list or modify `prompt` parameter

## Next Steps

Once you're happy with Ollama responses, integrate into HERA:
- Copy `ollama_service.py` pattern
- Add to Tier 2C (Root Cause Analysis)
- Or use in final response rendering
