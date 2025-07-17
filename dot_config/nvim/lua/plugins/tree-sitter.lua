return {
  {
    "nvim-treesitter/nvim-treesitter-context",
    lazy = true,
    opts = {}
  },
  {
    "yioneko/nvim-yati",
    lazy = true,
    event = { "VeryLazy" },
  },
  {
    "nvim-treesitter/nvim-treesitter",
    lazy = true,
    event = { "VeryLazy" },
    build = ":TSUpdate",
    config = function()
      local configs = require("nvim-treesitter.configs")

      configs.setup({
        ensure_installed = { "lua", "vim", "vimdoc", "javascript", "html", "rust", "tsx" },
        sync_install = false,
        highlight = { enable = true },
        yati = {
          enable = true,

          -- Whether to enable lazy mode (recommend to enable this if bad indent happens frequently)
          default_lazy = true,

          -- Determine the fallback method used when we cannot calculate indent by tree-sitter
          --   "auto": fallback to vim auto indent
          --   "asis": use current indent as-is
          --   "cindent": see `:h cindent()`
          -- Or a custom function return the final indent result.
          default_fallback = "auto"
        },
        indent = {
          enable = false -- disable builtin indent module
        }
      })
    end,
  }
}
