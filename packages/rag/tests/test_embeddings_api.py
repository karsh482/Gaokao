from openai import OpenAI

client = OpenAI(
    base_url='https://api-inference.modelscope.cn/v1',
    api_key='ms-b022ed32-3154-4448-92d2-ad4d56bce131', # ModelScope Token
)

response = client.embeddings.create(
    model='Qwen/Qwen3-Embedding-4B', # ModelScope Model-Id, required
    input='你好',
    encoding_format="float"
)

print(response.data)