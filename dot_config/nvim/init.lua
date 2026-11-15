-- lazy.nvim loading
local lazypath = vim.fn.stdpath "data" .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  vim.fn.system {
    "git",
    "clone",
    "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable", -- latest stable release
    lazypath,
  }
end
vim.opt.rtp:prepend(lazypath)

local opts = {
  defaults = {
    lazy = false,
  },
  performance = {
    cache = {
      enabled = true,
    },
  },
}

-- 環境変数を設定 
local uname = vim.loop.os_uname()

if uname.sysname == "Linux" then
  vim.g.os = "linux"
elseif uname.sysname == "Windows_NT" then
  vim.g.os = "windows"
end

-- slim プロファイルを読み込む
vim.g.slim_mode = true

-- 環境ごとにプロファイルをロード
if vim.g.vscode then
  require "vscode/keybinds"
  require("lazy").setup("vscode/plugins", opts)
  require "vscode/options"
elseif vim.g.slim_mode then
  require "slim/keybinds"
  require("lazy").setup("slim/plugins", opts)
  require "slim/options"
else
  require "rich/keybinds"
  require("lazy").setup("rich/plugins", opts)
  require "rich/options"
end

-- override設定があれば有効化
local function file_exists(path)
  local file = io.open(path, "r")
  if file then
    file:close()
    return true
  else
    return false
  end
end

if file_exists "override/options.lua" then
  require "override/options"
end

if file_exists "override/keybinds.lua" then
  require "override/keybinds"
end
