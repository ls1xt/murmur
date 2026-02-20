# .deb Package for Murmur

## Build

Requires fpm and uv on a Debian/Ubuntu machine:

```bash
sudo apt install ruby-dev
sudo gem install fpm
./packaging/deb/build-deb.sh
```

## Install

```bash
sudo dpkg -i murmur_0.1.0_amd64.deb
murmur config --key transcriber.api_key --value YOUR_KEY
murmur daemon start
```

## Notes

- Bundles assemblyai and customtkinter (not in Debian repos) into /opt/murmur/
- Requires portaudio19-dev and ydotool from apt
- For simpler install: `pip install murmur-dictation` works on any Linux
