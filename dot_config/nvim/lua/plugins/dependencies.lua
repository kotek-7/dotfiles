return {
  { 'nvim-tree/nvim-web-devicons', lazy = true },
  { 'BurntSushi/ripgrep', lazy = true },
  { "kkharji/sqlite.lua", lazy = true },
  { 'sharkdp/fd', lazy = true },
  { "nvim-lua/plenary.nvim", lazy = true },
  { "nvimtools/none-ls.nvim", lazy = true },
  {
    'rafamadriz/friendly-snippets',
    lazy = true,
    cond = false,
    config = function()
      require("luasnip.loaders.from_vscode").lazy_load()
    end,
  },
  {
    "MunifTanjim/nui.nvim",
  },
  {
    "rcarriga/nvim-notify",
    lazy = true,
    keys = {
      {
        "<leader>un",
        function()
          require("notify").dismiss({ silent = true, pending = true })
        end,
        desc = "Dismiss All Notifications",
      },
    },
    opts = {
      stages = "static",
      timeout = 3000,
      max_height = function()
        return math.floor(vim.o.lines * 0.75)
      end,
      max_width = function()
        return math.floor(vim.o.columns * 0.75)
      end,
      on_open = function(win)
        vim.api.nvim_win_set_config(win, { zindex = 100 })
      end,
    },
  },
  {
    "danielfalk/smart-open.nvim",
    lazy = true,
    branch = "0.2.x",
    config = function()
      require("telescope").load_extension("smart_open")
    end,
  },
  {
    "nvim-telescope/telescope-frecency.nvim",
    lazy = true,
    config = function()
      require("telescope").load_extension("frecency")
    end,
  },
  {
    "ahmedkhalf/project.nvim",
    lazy = true,
    config = function ()
      require('telescope').load_extension('projects')
    end
  }
}
