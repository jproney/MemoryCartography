# Create the visualization for figure 2 in the paper
library(ggplot2)

dat <- read.csv("fig2.csv", header = F)
names(dat) <- 1:5
dat <- reshape::melt(dat)
ggplot(dat, aes(x=variable, y=value)) + geom_boxplot(fill="dodgerblue") + theme(axis.text.x = element_text(face="bold", 
                                                                                                           size=22),
                                                                                axis.text.y = element_text(face="bold", 
                                                                                                           size=22))