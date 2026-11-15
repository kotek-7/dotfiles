return {
  "mason-org/mason-lspconfig.nvim",
  lazy = false,
  dependencies = {
    { "mason-org/mason.nvim", opts = {} },
    "neovim/nvim-lspconfig",
  },
  opts = {
    ensure_installed = {
      "lua_ls",
      "ts_ls",
      "html",
      "cssls",
    },
    automatic_enable = true,
  },
  init = function()
    vim.lsp.config("lua_ls", {
      settings = {
        Lua = {
          workspace = {
            checkThirdParty = false,
          },
        },
      },
    })
  end,
  keys = {
    {
      "<leader>ca",
      vim.lsp.buf.code_action,
      desc = "Code action",
    },
    {
      "<leader>cr",
      vim.lsp.buf.rename,
      desc = "Rename",
    },
    {
      "<leader>cf",
      function()
        vim.lsp.buf.format({ async = true })
      end,
      desc = "Format",
    },
  },
}

