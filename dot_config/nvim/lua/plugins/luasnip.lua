return {
  "L3MON4D3/LuaSnip",
  lazy = true,
  event = "InsertEnter",
  version = "v2.*",
  build = "make install_jsregexp",
  config = function()
    vim.keymap.set('n', '<leader>ss', require("luasnip.loaders").edit_snippet_files, { desc = "edit snippets" })
    require("luasnip.loaders.from_lua").load()
  end,
}
