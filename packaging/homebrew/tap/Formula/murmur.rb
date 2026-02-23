# Homebrew formula for Murmur — system-wide voice dictation for macOS.
#
# Tap:
#   brew tap ls1xt/murmur
#   brew install murmur
#
# Development HEAD install:
#   brew install --HEAD ls1xt/murmur/murmur
#
# Update SHA256 after tagging a new release:
#   Run: scripts/publish-tap.sh (from the murmur repo root)
class Murmur < Formula
  desc "System-wide voice dictation for macOS"
  homepage "https://github.com/ls1xt/murmur"
  url "https://github.com/ls1xt/murmur/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "PLACEHOLDER_RUN_scripts/publish-tap.sh"
  license "MIT"
  head "https://github.com/ls1xt/murmur.git", branch: "main"

  depends_on "portaudio"
  depends_on "python@3.13"
  depends_on "uv" => :build
  depends_on :macos

  def install
    venv = libexec

    # Create a virtualenv using the Homebrew-managed Python
    system Formula["uv"].opt_bin/"uv", "venv", venv,
           "--python", Formula["python@3.13"].opt_bin/"python3.13"

    # Let uv/pip install murmur + all deps from PyPI (network available during brew install)
    ENV["VIRTUAL_ENV"] = venv.to_s
    ENV.prepend_path "PKG_CONFIG_PATH", Formula["portaudio"].opt_lib/"pkgconfig"

    system Formula["uv"].opt_bin/"uv", "pip", "install",
           "--python", "#{venv}/bin/python3",
           buildpath.to_s

    # Link the murmur CLI into Homebrew's bin
    bin.install_symlink Dir["#{libexec}/bin/murmur"]
  end

  test do
    system bin/"murmur", "--help"
  end
end
