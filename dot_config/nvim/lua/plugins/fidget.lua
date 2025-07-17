local function isPath(inputString)
  return string.find(inputString, "[/\\]")
end

local function splitString(inputString)
  local splittedStrings = {}
  for word in string.gmatch(inputString, "%S+") do
    table.insert(splittedStrings, word)
  end
  return splittedStrings
end

local function removePathFromString(inputString)
  local splittedStrings = splitString(inputString)

  local processedStrings = {}
  for _,word in ipairs(splittedStrings) do
    if not isPath(word) then
      table.insert(processedStrings, word)
    end
  end

  local processedString = ""
  for i,word in ipairs(processedStrings) do
    if i == #processedStrings then
      processedString = processedString..word
    else
      processedString = processedString..word.." "
    end
  end

  return processedString
end

return {
  "j-hui/fidget.nvim",
  lazy = true,
  event = "LspAttach",
  config = function ()
    local fidget = require("fidget");
    fidget.setup {
      notification = {
        window = {
          winblend = 0,
          relative = "editor",
        },
      },
      progress = {
        display = {
          format_message = function(msg)
            local message = ""
            if not msg.message then
              message = msg.done and "Completed" or "In progress..."
            else
              message = removePathFromString(msg.message)
            end
            if msg.percentage ~= nil then
              message = string.format("%s (%.0f%%)", message, msg.percentage)
            end
            return message
          end,
          format_annote = function(msg)
            return msg.title
          end,
          overrides = {
            rust_analyzer = {
              name = "Rust Analyzer",
              icon = fidget.progress.display.for_icon(fidget.spinner.animate("arrow", 2.5), "🦀"),
              update_hook = function(item)
                require("fidget.notification").set_content_key(item)
                if item.hidden == nil and string.match(item.annote, "clippy") then
                  -- Hide clippy-related notifications
                  item.hidden = true
                end
              end,
            },
          }
        }
      }
    }
  end,
  tag = "legacy"
}
