set -e

sudo apt-get update
sudo apt-get install -y build-essential curl git zsh pkg-config libssl-dev

# setup chezmoi
sh -c "$(curl -fsLS https://get.chezmoi.io)" -- init --apply kotek-7

# setup mise
sh -c "$(curl -fsSL https://mise.run)"
eval "$(mise activate zsh)"
~/.local/bin/mise install

# zsh setup
sudo chsh -s $(which zsh)
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended --keep-zshrc --skip-chsh
git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions
