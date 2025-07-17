return {
  "nvim-tree/nvim-tree.lua",
  lazy = true,
  version = "*",
  keys = {
    { "<leader>e", mode = "n"},
  },
  cmd = {
    "NvimTreeToggle",
    "NvimTreeOpen",
    "NvimTreeClose",
    "NvimTreeFocus",
  },
  config = function()
    vim.keymap.set('n', '<leader>e', '<cmd>NvimTreeToggle<CR>')

    require("nvim-tree").setup {
      hijack_cursor = true,
      disable_netrw = true,
      sync_root_with_cwd = true,
      respect_buf_cwd = true,
      reload_on_bufenter = true,
      renderer = {
        icons = {
          show = {
            modified = true
          }
        }
      },
      update_focused_file = {
        enable = true,
      },
      diagnostics = {
        enable = true,
      },
      modified = {
        enable = true,
      },
    }
  end,
}
