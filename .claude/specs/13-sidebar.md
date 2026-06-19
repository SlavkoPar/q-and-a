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
- create `other answers` section 
- on select question

   --  in `answer section` display one of the assigned-answers of that 
   question with two buttons `Fixed` and `Not Fixed`, on click to `Not Fixed` show next `assigned-answer`, on click on 'Fixed' increment `numOf_Fixed_clicks` in table `question-answers`, for that `question answer`

   --  in `other answers` section display answers the satisfy at least one word of question as the filter, show max of 10 answers, ordered by best matching, upon click on answer increment `numOf_Fixed_clicks` in table `question-answers`, for that `question answer`



## Definition of done
