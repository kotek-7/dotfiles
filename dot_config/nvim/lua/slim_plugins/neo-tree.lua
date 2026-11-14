return {
  "nvim-neo-tree/neo-tree.nvim",
  lazy = false, -- neo-tree will lazily load itself
  branch = "v3.x",
  opts = {},
  keys = {
    { mode = "n", "<C-e>", "<cmd>Neotree toggle<CR>", {} },
  },
}
