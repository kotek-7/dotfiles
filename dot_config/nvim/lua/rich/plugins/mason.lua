return {
  "williamboman/mason.nvim",
  lazy = false,
  build = ":MasonUpdate",
  config = function()
    require("mason").setup()
  end,
}
