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

  -- Fuzzy finder
  {
    "nvim-mini/mini.pick",
    lazy = true,
    opts = {},
    keys = {
      {
        "<leader><leader>",
        function() MiniPick.builtin.files() end,
        desc = "Find files",
      },
      {
        "<leader>ff",
        function() MiniPick.builtin.files() end,
        desc = "Find files",
      },
      {
        "<leader>fg",
        function() MiniPick.builtin.grep_live() end,
        desc = "Live grep",
      },
      {
        "<leader>fb",
        function() MiniPick.builtin.buffers() end,
        desc = "Buffers",
      },
      {
        "<leader>fh",
        function() MiniPick.builtin.help() end,
        desc = "Help",
      },
    },
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
