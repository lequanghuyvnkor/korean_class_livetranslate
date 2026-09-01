import sounddevice as sd

print("=== SoundDevice Input Devices ===")
devs = sd.query_devices()
for idx, dev in enumerate(devs):
    if dev['max_input_channels'] > 0:
        print(f"ID: {idx} | Name: {dev['name']} | Channels: {dev['max_input_channels']}")
