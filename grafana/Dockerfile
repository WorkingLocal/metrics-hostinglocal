FROM grafana/grafana:11.6.2
USER root
COPY assets/hl-logo.png /usr/share/grafana/public/img/hl-logo.png
RUN cat /usr/share/grafana/public/build/grafana.dark.23c5425b7a9e1580d499.css > /tmp/dark-backup.css
COPY custom.css /tmp/custom-hl.css
RUN cat /tmp/custom-hl.css >> /usr/share/grafana/public/build/grafana.dark.23c5425b7a9e1580d499.css
USER grafana
