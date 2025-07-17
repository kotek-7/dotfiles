local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  vim.fn.system({
    "git",
    "clone",
    "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable", -- latest stable release
    lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

local opts = {
  defaults = {
    lazy = false,
  },
  performance = {
    cache = {
      enabled = true,
    }
  }
}

local uname = vim.loop.os_uname()

if uname.sysname == "Linux" then
  vim.g.os = "linux"
elseif uname.sysname == "Windows_NT" then
  vim.g.os = "windows"
end

vim.g.slim_mode = true

if vim.g.neovide then
  require("base/neovide_options")
  require("base/neovide_keybinds")
elseif vim.g.vscode then
  require("base/vscode_keybinds")
  require("lazy").setup("vscode_plugins", opts)
  require("base/vscode_options")
elseif vim.g.slim_mode then
  require("base/slim_keybinds")
  require("lazy").setup("slim_plugins", opts)
  require("base/slim_options")
else
  require("base/keybinds")
  require("lazy").setup("plugins", opts)
  require("base/options")
end

local function file_exists(path)
  local file = io.open(path, "r")
  if file then
    file:close()
    return true
  else
    return false
  end
end

if file_exists("base/override_options.lua") then
  require("base/override_options")
end

if file_exists("base/override_keybinds.lua") then
  require("base/override_keybinds")
end
