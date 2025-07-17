return {
  "lewis6991/gitsigns.nvim",
  lazy = true,
  event = "VeryLazy",
  opts = {
    current_line_blame = true,
    current_line_blame_opts = {
      delay = 0
    }
  },
  keys = {
    { "<leader>tb", function() require("gitsigns").toggle_current_line_blame() end, mode = "n", desc = "Toggle Blame" }
  }
}
