from ollama import chat

stream = chat(
  model='gemma4:e4b',
  messages=[{'role': 'user', 'content': 'hãy giới thiệu bạn là ai đi'}],
  stream=True,
)

content = ''
for chunk in stream:
  if chunk.message.content:
    print(chunk.message.content, end='', flush=True)
    content += chunk.message.content

  # append the accumulated content to the messages for the next request
  new_messages = [{ "role": "assistant", "content": content }]