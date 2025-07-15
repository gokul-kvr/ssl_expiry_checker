import base64

# Read the token.json file
with open("token.json", "rb") as f:
    encoded = base64.b64encode(f.read()).decode("utf-8")

# Save it to token.b64 (optional)
with open("token.b64", "w") as f:
    f.write(encoded)

# Print to copy-paste into GitHub Secret
print(encoded)
