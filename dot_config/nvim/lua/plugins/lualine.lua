local function esc(x)
  return (
    x:gsub("%%", "%%%%")
    :gsub("^%^", "%%^")
    :gsub("%$$", "%%$")
    :gsub("%(", "%%(")
    :gsub("%)", "%%)")
    :gsub("%.", "%%.")
    :gsub("%[", "%%[")
    :gsub("%]", "%%]")
    :gsub("%*", "%%*")
    :gsub("%+", "%%+")
    :gsub("%-", "%%-")
    :gsub("%?", "%%?")
  )
end

local function get_cwd()
  local cwd = vim.uv.cwd()
  local git_dir = require("lualine.components.branch.git_branch").find_git_dir(cwd)
  local root = vim.fs.dirname(git_dir)
  if cwd == root then
    return ""
  end
  local d, n = string.gsub(cwd, esc(root) .. "/", "")
  if n == 0 and d == nil then
    return ""
  end
  return "(" .. d .. ")"
end

local function is_available_lspsaga()
  local ok, _ = pcall(require, "lspsaga")
  if not ok then
    return false
  end
  return true
end

return {
  {
    'nvim-lualine/lualine.nvim',
    lazy = true,
    event = "VimEnter",
    priority = 800,
    opts = {
      options = {
        theme = 'auto',
        globalstatus = true,
        section_separators = {},
        component_separators = {}
      },
      sections = {
        lualine_a = { "mode" },
        lualine_b = { { "filetype", icon_only = true }, { "filename", path = 1 },  },
        lualine_c = { { get_cwd }, { 'require("lspsaga.symbolwinbar"):get_winbar()', cond = is_available_lspsaga } },
        lualine_x = { "require'lsp-status'.status()", "diagnostics", "overseer" },
        lualine_y = { "branch", "diff" },
        lualine_z = {
          function()
            return " " .. os.date("%R")
          end,
        },
      },
      inactive_sections = {
        lualine_a = {},
        lualine_b = {},
        lualine_c = { {
          'filename',
          file_status = true, -- displays file status (readonly status, modified status)
          path = 1            -- 0 = just filename, 1 = relative path, 2 = absolute path
        } },
        lualine_x = { "location" },
        lualine_y = {},
        lualine_z = {},
      },
      tabline = {},
      extentions = {}
    }
  } 
}
