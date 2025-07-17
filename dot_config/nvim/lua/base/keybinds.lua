-- leaderキー
vim.g.mapleader = ' ';

-- window移動
vim.keymap.set('n', '<C-h>', '<C-w><C-h>')
vim.keymap.set('n', '<C-j>', '<C-w><C-j>')
vim.keymap.set('n', '<C-k>', '<C-w><C-k>')
vim.keymap.set('n', '<C-l>', '<C-w><C-l>')

-- window size
vim.keymap.set('n', '<C-Up>', '<C-w>+')
vim.keymap.set('n', '<C-Down>', '<C-w>-')
vim.keymap.set('n', '<C-Left>', '<C-w><')
vim.keymap.set('n', '<C-Right>', '<C-w>>')

-- Clear search with <esc>
vim.keymap.set({ "i", "n" }, "<esc>", "<cmd>noh<cr><esc>", { desc = "Escape and Clear hlsearch" })

-- 画面スクロール
vim.keymap.set('n', '<left>', 'zh')
vim.keymap.set('n', '<down>', 'zj')
vim.keymap.set('n', '<up>', 'zk')
vim.keymap.set('n', '<right>', 'zl')

-- buffer移動
vim.keymap.set('n', '<S-l>', ':bnext<CR>', { silent = true })
vim.keymap.set('n', '<S-h>', ':bprev<CR>', { silent = true })

-- ZZ,ZQを無効
vim.keymap.set('n', 'ZZ', '<NOP>')
vim.keymap.set('n', 'ZQ', '<NOP>')

-- put後行末に移動
vim.keymap.set({ 'n', 'v' }, 'p', 'p`]')

-- pをレジスタに登録しない
vim.keymap.set({ 'n', 'v' }, 'p', '"_dP', { desc = "Paste without yanking" })

-- レジスタに登録しない
vim.keymap.set('n', 'x', '"_x')
vim.keymap.set('n', 'X', '"_X')
vim.keymap.set('n', 's', '"_s')
vim.keymap.set('n', 'S', '"_S')
vim.keymap.set('n', 'c', '"_c')
vim.keymap.set('n', 'C', '"_C')

-- 行を追加
vim.keymap.set('n', '<leader>o', 'o<esc>')
vim.keymap.set('n', '<leader><S-o>', '<S-o><esc>')

-- C-zを無効化
vim.keymap.set('n', '<C-z>', '<NOP>')

-- 保存
vim.keymap.set({ "i", "x", "n", "s" }, "<C-s>", "<cmd>w<cr><cmd>NvimTreeClose<cr><cmd>mks!<cr>", { desc = "Save File" })