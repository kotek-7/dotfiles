return {
  -- Editing
  {
    "nvim-mini/mini.ai",
    event = "VeryLazy",
    opts = {},
  },
  {
    "nvim-mini/mini.surround",
    event = "VeryLazy",
    opts = {},
  },
  {
    "nvim-mini/mini.pairs",
    event = "InsertEnter",
    opts = {},
  },
  {
    "nvim-mini/mini.bracketed",
    event = "VeryLazy",
    opts = {},
  },

  -- Navigation
  {
    "nvim-mini/mini.jump",
    lazy = false,
    opts = {},
  },
  {
    "nvim-mini/mini.jump2d",
    lazy = true,
    opts = {},
    keys = {
      {
        ";",
        function()
          local jump = require("mini.jump2d")
          jump.start(jump.builtin_opts.query)
        end,
        mode = { "n", "x", "o" },
        desc = "Jump",
      },
    },
  },
}
