# Biographical Interviewer AI Guide

## Overview

Your LangGraph agent has been transformed into a compassionate biographical interviewer designed to help preserve the life stories and memories of deceased loved ones through thoughtful interviews with family members and friends.

## How to Use the Different Interview Modes

### 1. General Biographical Interview (Default)

**When to use**: For comprehensive interviews covering all aspects of a person's life. The AI automatically handles relationship discovery, whether it's the first session or a follow-up.

```yaml
deceased_name: "Robert Chen"
interviewee_name: "Sarah Chen"
```

This mode intelligently adapts to:

- **First meetings**: Establishes trust and discovers relationships naturally
- **Known relationships**: Uses provided relationship info to personalize questions
- **Shared last names**: Makes gentle inferences about family connections
- **Unknown relationships**: Explores the connection through careful questioning

**Configuration**:

```yaml
system_prompt: CHILDHOOD_MEMORIES_PROMPT
interview_style: childhood
```

## Configuration Tips

### Simple Configuration Setup

Just configure these two essential fields:

```yaml
deceased_name: "Margaret Johnson"
interviewee_name: "Susan Chen"
```

The AI will automatically:

- **Detect relationships** based on shared/different last names
- **Adapt its approach** once the relationship is discovered
- **Personalize all questions** using the names provided

**Test Setup**: The system comes with placeholder names "Robert Chen" and "Sarah Chen" for easy testing.

## Sample Interview Flow

### Session 1: Initial Interview

- Use default `SYSTEM_PROMPT`
- AI automatically handles relationship discovery and trust building
- Focus on getting a comprehensive life overview
- Identify key themes for future focused sessions

### Session 2-4: Deep Dives

- Use `DEEP_DIVE_SESSION_PROMPT`
- Focus on specific life periods or themes identified in Session 1
- Examples: Career years, parenting phase, retirement, etc.

### Session 5: Family Dynamics

- Use `FAMILY_DYNAMICS_PROMPT`
- Explore relationships with spouse, children, siblings, parents
- Handle sensitive topics with extra care

### Session 6: Legacy

- Use `LEGACY_AND_MEANING_PROMPT`
- Focus on lasting impact and what the person meant to others
- Often the most emotional session

### Session 7: Childhood (if applicable)

- Use `CHILDHOOD_MEMORIES_PROMPT`
- Best with family members who knew them as children
- Reveals formative experiences and early personality

## Best Practices

### Before Starting

1. Set the deceased person's name in configuration
2. Choose appropriate interview mode for the session
3. Consider any cultural context that might be relevant
4. Ensure a comfortable, private environment for the interviewee

### During Interviews

- Let the AI guide the conversation flow naturally
- Don't rush - allow for pauses and emotional moments
- Follow up on interesting details the AI might identify
- Be prepared to switch modes if the conversation naturally evolves

### After Each Session

- Review what themes emerged for future deep dives
- Note any sensitive areas that need careful handling
- Consider which family members might have different perspectives on the same events

## Complete Sample Interview

See `SAMPLE_INITIAL_INTERVIEW.md` for a full example of an opening session interview between the AI and Sarah Chen, discussing her deceased father Robert Chen. This example shows:

- How to set up the configuration with personalized names and relationships
- A realistic conversation flow with emotional moments
- How the AI handles tears, pauses, and sensitive topics
- The types of follow-up questions that naturally emerge
- Analysis and planning for future interview sessions

This sample demonstrates the AI's empathetic approach and gives you a template for what to expect.

## Example Questions the AI Will Ask

### Opening Session (Relationship Discovery)

**When relationship is known:**

- "As [Name]'s daughter, you must have so many meaningful memories..."
- "What comes to mind when you think of [Name]?"

**When same last name but relationship unknown:**

- "I notice you both share the Johnson name - I imagine you must be family. Could you tell me about your relationship with [Name]?"
- "What was [Name] like as a [father/brother/grandfather]?"

**When relationship is completely unknown:**

- "Would you mind sharing how you knew [Name]? I'd love to understand your connection."
- "What kind of person was [Name] to you?"

### Deep Dive Sessions

- "Paint me a picture of what a typical day was like for [Name] during that time..."
- "Can you share a story that really captures who [Name] was?"
- "What was going through [Name]'s mind during that period?"

### Family Dynamics

- "How did [Name] show love to family members?"
- "Was [Name] the type to give advice, or did they lead by example?"
- "How did [Name] handle family disagreements or conflicts?"

### Legacy Sessions

- "What did [Name] teach you that you carry with you today?"
- "How do you see [Name]'s influence in your children/family?"
- "What would [Name] want people to remember about them?"

## Technical Notes

- The AI will automatically adapt its questioning style based on the configured mode
- It's designed to handle emotional responses with sensitivity
- The conversation will flow naturally - you don't need to follow a strict script
- You can change configurations between sessions to focus on different aspects

## Tips for Family Members Being Interviewed

### What to Expect

- Questions will start general and become more specific
- The AI will ask for stories rather than just facts
- It's okay to take breaks or skip difficult topics
- There are no "wrong" answers - all perspectives are valuable

### How to Prepare

- Think about your favorite memories beforehand
- Consider bringing photos or mementos that might spark memories
- Know that contradictions between family members' stories are normal
- Remember that this is about honoring your loved one's memory

## Common Emotional Moments and How the AI Handles Them

- **Tears**: AI will acknowledge emotions and offer breaks
- **Difficult memories**: AI won't push but will listen if you want to share
- **Family conflicts**: AI focuses on your perspective without judgment
- **Memory gaps**: AI reassures that it's okay not to remember everything

This biographical interviewer is designed to create a comprehensive, compassionate record of a life well-lived. Each conversation contributes to preserving someone's legacy for future generations.
