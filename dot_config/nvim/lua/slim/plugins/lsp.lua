return {
  "neovim/nvim-lspconfig",
  lazy = false,
  config = function()
    vim.lsp.config("lua_ls", {
      settings = {
        Lua = {
          workspace = {
            checkThirdParty = false,
          },
        },
      },
    })

    vim.lsp.enable({
      "lua_ls",
      "ts_ls",
      "html",
      "cssls",
    })

    vim.keymap.set("n", "<leader>cf",
      vim.lsp.buf.format, { desc = "Format" })

    vim.keymap.set("n", "<leader>ca",
      vim.lsp.buf.code_action, { desc = "Code action" })

    vim.keymap.set("n", "<leader>cr",
      vim.lsp.buf.rename, { desc = "Rename" })
  end,
}
