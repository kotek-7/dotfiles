# dotfiles
## Installation
```bash
sudo apt-get update
sudo apt-get install -y curl build-essential curl git zsh pkg-config libssl-dev
sh -c "$(curl -fsLS https://raw.githubusercontent.com/kotek-7/dotfiles/refs/heads/main/init.sh)"
sudo chsh -s "$(command -v zsh)" "$USER"
```
