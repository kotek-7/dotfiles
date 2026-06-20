set -e

# setup chezmoi
sh -c "$(curl -fsLS https://get.chezmoi.io)" -- init --apply kotek-7

# setup mise
sh -c "$(curl -fsSL https://mise.run)"
~/.local/bin/mise install

# zsh setup
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended --keep-zshrc --skip-chsh
git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions
