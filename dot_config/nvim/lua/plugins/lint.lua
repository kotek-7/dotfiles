return {
  "mfussenegger/nvim-lint",
  lazy = true,
  event = { "BufReadPre", "BufNewFile" },
  cond = false,
  config = function()
    local lint = require("lint")
    lint.linters_by_ft = {
      javascript = { 'eslint', },
      typescript = { 'eslint', },
      javascriptreact = { 'eslint', },
      typescriptreact = { 'eslint', },
      vue = { 'eslint', },
      lua = { 'luacheck', },
    }
    vim.api.nvim_create_autocmd("BufWritePost", {
      group = vim.api.nvim_create_augroup("lint", { clear = true }),
      callback = function()
        lint.try_lint()
      end
    })
  end
}
