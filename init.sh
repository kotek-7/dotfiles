apt-get update
apt-get install -y build-essential curl git

# install brew
NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv bash)"

# install brew packages
brew install zsh mise chezmoi

# initialize dotfiles
chezmoi init --apply kotek-7

# zsh setup
chsh -s $(which zsh)
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended

# mise setup
eval "$(mise activate zsh)"
mise install

exit 0
