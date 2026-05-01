set -euo pipefail

apt-get update
apt-get install -y build-essential curl git zsh pkg-config libssl-dev

# install chezmoi
sh -c "$(curl -fsLS https://get.chezmoi.io)"

# install mise
sh -c "$(curl -fsSL https://mise.run)"

# initialize dotfiles
chezmoi init --apply kotek-7

# zsh setup
chsh -s $(which zsh)
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended --keep-zshrc --skip-chsh
git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions

# mise setup
eval "$(mise activate zsh)"
mise install
