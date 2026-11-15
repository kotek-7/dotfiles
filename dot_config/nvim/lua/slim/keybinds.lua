-- leaderキー
vim.g.mapleader = " "

-- window移動
vim.keymap.set("n", "<C-h>", "<C-w><C-h>", { desc = "Focus left window" })
vim.keymap.set("n", "<C-j>", "<C-w><C-j>", { desc = "Focus below window" })
vim.keymap.set("n", "<C-k>", "<C-w><C-k>", { desc = "Focus above window" })
vim.keymap.set("n", "<C-l>", "<C-w><C-l>", { desc = "Focus right window" })

-- window size
vim.keymap.set("n", "<C-Up>", "<C-w>+", { desc = "Increase window height" })
vim.keymap.set("n", "<C-Down>", "<C-w>-", { desc = "Decrease window height" })
vim.keymap.set("n", "<C-Left>", "<C-w><", { desc = "Decrease window width" })
vim.keymap.set("n", "<C-Right>", "<C-w>>", { desc = "Increase window width" })

-- 画面スクロール
vim.keymap.set("n", "<Left>", "zh", { desc = "Scroll left" })
vim.keymap.set("n", "<Down>", "zj", { desc = "Scroll down one screen line" })
vim.keymap.set("n", "<Up>", "zk", { desc = "Scroll up one screen line" })
vim.keymap.set("n", "<Right>", "zl", { desc = "Scroll right" })

-- buffer移動
vim.keymap.set("n", "<S-l>", ":bnext<CR>", { desc = "Next buffer", silent = true })
vim.keymap.set("n", "<S-h>", ":bprev<CR>", { desc = "Previous buffer", silent = true })

-- ZZ,ZQを無効
vim.keymap.set("n", "ZZ", "<Nop>", { desc = "Disable save and quit" })
vim.keymap.set("n", "ZQ", "<Nop>", { desc = "Disable quit without saving" })

-- レジスタに登録しない
vim.keymap.set("n", "x", '"_x', { desc = "Delete character (black hole)" })
vim.keymap.set("n", "X", '"_X', { desc = "Delete previous character (black hole)" })
vim.keymap.set("n", "s", '"_s', { desc = "Substitute character (black hole)" })
vim.keymap.set("n", "S", '"_S', { desc = "Substitute line (black hole)" })
vim.keymap.set("n", "c", '"_c', { desc = "Change text (black hole)" })
vim.keymap.set("n", "C", '"_C', { desc = "Change to end of line (black hole)" })

-- 行を追加
vim.keymap.set("n", "<Leader>o", "o<Esc>", { desc = "Insert blank line below" })
vim.keymap.set("n", "<Leader><S-o>", "<S-o><Esc>", { desc = "Insert blank line above" })

-- C-zを無効化
vim.keymap.set("n", "<C-z>", "<Nop>", { desc = "Disable suspend" })
