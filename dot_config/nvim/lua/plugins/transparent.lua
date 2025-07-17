return {
  "xiyaowong/transparent.nvim",
  config = function ()
    require("transparent").setup {
      auto = true,
      extra_groups = { }
    }
    require("transparent").clear_prefix("BufferLine")
  end,
  priority = 900,
  lazy = false,
  keys = {
    { "<leader>tt", "<cmd>TransparentToggle<CR>", mode = "n", desc = "Toggle Transparent" }
  }
}
