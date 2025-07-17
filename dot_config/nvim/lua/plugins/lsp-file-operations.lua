return {
  {
    "antosha417/nvim-lsp-file-operations",
    lazy = true,
    cmd = {
      "NvimTreeOpen"
    },
    config = function()
      require("lsp-file-operations").setup()
    end,
  },
}
