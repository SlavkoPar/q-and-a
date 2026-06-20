# Spec: Sidebar


## Overview

## Depends on
- Step 12: final

## Routes

## Database changes


## 12. Expected Behavior


## Templates

## Files to change
- Add `INTEGER` field `numOf_Fixed_clicks`, in table `question-answers`

## Files to create


## New dependencies
No new dependencies. 


## Rules for implementation

- create an animated, closable right `sidebar` side navigation menu 
- put hamburger icon in menu bar to the right side
- inside of side bar implement autocomplete filter for questions
- create `answer section` below the filter
- on select question 
   -- select all answers from table `answers` which satisfy at least one word of selected question, set `numOf_Fixeds` for them
   -- append answers from question assigned-answers
   -- order all answers by numOf_Fixed desc
   
   -- display one of the answers with two buttons `Fixed` and `Not Fixed`
   -- on click to `Not Fixed` show next `answer`, 
   -- on click on 'Fixed', if row exists in table `question-answers`increment increment `numOf_Fixed`, otherwise create a new row in table `question-answers`


## Definition of done
