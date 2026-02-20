# NOTE: sha256 values are placeholders. Before submitting to Homebrew:
# 1. Publish murmur-dictation to PyPI first (see scripts/publish.sh)
# 2. Run: brew audit --new packaging/homebrew/murmur.rb
# 3. Or regenerate with: pip install homebrew-pypi-poet && poet -f murmur-dictation
# 4. Update all PLACEHOLDER sha256 values with actual hashes
# 5. Create tap: https://docs.brew.sh/How-to-Create-and-Maintain-a-Tap
#
# Note: PyPI package is named "murmur-dictation" (murmur was already taken).
class Murmur < Formula
  include Language::Python::Virtualenv

  desc "System-wide voice dictation for Linux and macOS"
  homepage "https://github.com/berleon/murmur"
  # Update URL and sha256 after publishing to PyPI:
  url "https://files.pythonhosted.org/packages/source/m/murmur-dictation/murmur_dictation-0.1.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256_AFTER_PYPI_PUBLISH"
  license "MIT"
  head "https://github.com/berleon/murmur.git", branch: "main"

  depends_on "python@3.11"
  depends_on "portaudio"

  # Core dependencies — sha256 values are placeholders; update after first publish.
  # Run: brew fetch --build-from-source packaging/homebrew/murmur.rb
  # Or use homebrew-pypi-poet to regenerate: pip install homebrew-pypi-poet && poet -f murmur-dictation
  resource "assemblyai" do
    url "https://files.pythonhosted.org/packages/source/a/assemblyai/assemblyai-0.52.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "pystray" do
    url "https://files.pythonhosted.org/packages/source/p/pystray/pystray-0.19.5.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "Pillow" do
    url "https://files.pythonhosted.org/packages/source/P/Pillow/Pillow-10.0.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "sounddevice" do
    url "https://files.pythonhosted.org/packages/source/s/sounddevice/sounddevice-0.5.5.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "pynput" do
    url "https://files.pythonhosted.org/packages/source/p/pynput/pynput-1.7.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "pyobjc-framework-ApplicationServices" do
    url "https://files.pythonhosted.org/packages/source/p/pyobjc-framework-ApplicationServices/pyobjc-framework-ApplicationServices-9.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "customtkinter" do
    url "https://files.pythonhosted.org/packages/source/c/customtkinter/customtkinter-5.2.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    system bin/"murmur", "--help"
  end
end
