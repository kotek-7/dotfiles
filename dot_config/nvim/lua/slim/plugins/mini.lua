return {
  -- UI
  {
    "nvim-mini/mini.icons",
    lazy = false,
    opts = {},
  },
  {
    "nvim-mini/mini.statusline",
    lazy = false,
    opts = {},
  },
  {
    "nvim-mini/mini.tabline",
    lazy = false,
    opts = {},
  },
  {
    "nvim-mini/mini.clue",
    lazy = false,
    opts = {
      triggers = {
        -- Leader triggers
        { mode = { 'n', 'x' }, keys = '<Leader>' },

        -- `[` and `]` keys
        { mode = 'n',          keys = '[' },
        { mode = 'n',          keys = ']' },

        -- Built-in completion
        { mode = 'i',          keys = '<C-x>' },

        -- `g` key
        { mode = { 'n', 'x' }, keys = 'g' },

        -- Marks
        { mode = { 'n', 'x' }, keys = "'" },
        { mode = { 'n', 'x' }, keys = '`' },

        -- Registers
        { mode = { 'n', 'x' }, keys = '"' },
        { mode = { 'i', 'c' }, keys = '<C-r>' },

        -- Window commands
        { mode = 'n',          keys = '<C-w>' },

        -- `z` key
        { mode = { 'n', 'x' }, keys = 'z' },
      },

      clues = {
        -- Enhance this by adding descriptions for <Leader> mapping groups
        require(miniclue).gen_clues.square_brackets(),
        require(miniclue).gen_clues.builtin_completion(),
        require(miniclue).gen_clues.g(),
        require(miniclue).gen_clues.marks(),
        require(miniclue).gen_clues.registers(),
        require(miniclue).gen_clues.windows(),
        require(miniclue).gen_clues.z(),
      },
    }
  },
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

  -- Files
  {
    "nvim-mini/mini.files",
    lazy = true,
    opts = {},
    keys = {
      {
        "<C-e>",
        function()
          local files = require("mini.files")
          local path = vim.api.nvim_buf_get_name(0)
          files.open(path ~= "" and path or nil)
        end,
        desc = "File explorer",
      },
    },
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

  -- Git
  {
    "nvim-mini/mini.diff",
    event = { "BufReadPost", "BufNewFile" },
    opts = {},
  },
  {
    "nvim-mini/mini-git",
    cmd = "Git",
    opts = {},
  },

  -- Snippets
  {
    "nvim-mini/mini.snippets",
    lazy = false,
    opts = function()
      return {
        snippets = {
          require("mini.snippets").gen_loader.from_lang(),
        },
      }
    end,
  },

  -- Completion
  {
    "nvim-mini/mini.completion",
    event = "InsertEnter",
    opts = {},
  },

  -- Navigation
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
