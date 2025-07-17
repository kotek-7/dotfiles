vim.opt.termguicolors = true

vim.opt.scrolloff = 4
vim.opt.clipboard = "unnamedplus"
vim.opt.encoding = "utf-8"
vim.opt.fileencoding = "utf-8"

vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.cursorline = true
vim.opt.signcolumn = "yes:1"
vim.opt.wrap = false
vim.opt.list = true
vim.opt.laststatus = 3

vim.opt.swapfile = false
vim.opt.tabstop = 2
vim.opt.expandtab = true
vim.opt.smartindent = true
vim.opt.shiftwidth = 2

-- nvim-tree
vim.g.loaded_netrw = 1
vim.g.loaded_netrwPlugin = 1

vim.g.sqlite_clib_path = "sqlite3.dll"

vim.diagnostic.config({
  underline = true
})
